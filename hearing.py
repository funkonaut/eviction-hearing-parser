import os
import re

from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

import fetch_page


def get_test_html_path(index: int, page_type: str) -> str:
    this_directory = os.path.dirname(os.path.realpath(__file__))
    test_filepath = os.path.join(this_directory, page_type, f"example_{index}.html")
    return test_filepath


def load_soup_from_filepath(filepath: str) -> BeautifulSoup:
    with open(filepath) as fp:
        soup = BeautifulSoup(fp, "html.parser")
    return soup


def get_test_soup(index: int) -> BeautifulSoup:
    filepath = get_test_html_path(index, page_type="test_pages")
    return load_soup_from_filepath(filepath)


def get_test_search_page(index: int) -> BeautifulSoup:
    filepath = get_test_html_path(index, page_type="test_search_pages")
    return load_soup_from_filepath(filepath)


def get_plaintiff(soup):
    # TODO handle multiple plaintiffs
    tag = get_plaintiff_elements(soup)[0]
    name_elem = tag.find_next_sibling("th")

    return name_elem.text


def get_plaintiff_elements(soup):
    """
    Gets the plaintiff HTML elements from a CaseDetail.
    These are currently used as an anchor for most of the Party Info parsing.
    """
    return soup.find_all("th", text="Plaintiff")


def get_defendant_elements(soup):
    """
    Gets the defendant HTML elements from a CaseDetail.
    These are currently used as an anchor for most of the Party Info parsing.
    """
    return soup.find_all("th", text="Defendant")


def get_defendants(soup):
    defendants = []
    for tag in get_defendant_elements(soup):
        name_elem = tag.find_next_sibling("th")
        defendants.append(name_elem.text)
    together = "; ".join(defendants)
    return together


def get_case_number(soup):
    elem = soup.find(class_="ssCaseDetailCaseNbr").span
    return elem.text


def get_style(soup):
    elem = soup.find_all("table")[4].tbody.tr.td
    return elem.text


def get_zip(party_info_th_soup) -> str:
    """Returns a ZIP code from the Table Heading Party Info of a CaseDetail"""
    zip_regex = re.compile(r", tx \d{5}(-\d{4})?")

    def has_zip(string: str) -> bool:
        return bool(zip_regex.search(string.lower()))

    zip_tag = party_info_th_soup.find_next(string=has_zip)
    return zip_tag.strip().split()[-1] if zip_tag is not None else ""


def get_disposition_tr_element(soup) -> str:
    """
    Returns the <tr> element of a CaseDetail document that contains Disposition info, if one exists.
    """
    disp_date_th = soup.find(
        "th", id=lambda id_str: id_str is not None and "RDISPDATE" in id_str
    )
    return disp_date_th.parent if disp_date_th is not None else None


def get_disposition_type(disposition_tr) -> str:
    return disposition_tr.find("b").text


def get_disposition_amount(disposition_tr) -> str:
    judgement_field = disposition_tr.find("span")
    return judgement_field.text if judgement_field is not None else ""


def get_disposition_winning_party(disposition_tr, plaintiff) -> str:
    """
    Looks for part of the plaintiff's name in the awarded to field of a disposition.
    Name orders may be different in different parts of the document.
    """
    print(disposition_tr)
    award_field = disposition_tr.find(text=re.compile(r"Awarded To:"))

    if award_field is None:
        return "N/A"
    winner = award_field.next_sibling.text

    return "PLAINTIFF" if plaintiff.split()[0] in winner else "DEFENDANT"


def get_hearing_tag(soup):
    """
    Returns the element in the Events and Hearings section of a CaseDetail document
    that holds the most recent hearing info if one has taken place.
    """

    def ends_with_hearing(string: str) -> bool:
        return string.endswith("Hearing")

    hearings = soup.find_all("b", string=ends_with_hearing)
    return hearings[-1] if len(hearings) > 0 else None


def get_hearing_text(soup) -> str:
    hearing_tag = get_hearing_tag(soup)
    return hearing_tag.next_sibling if hearing_tag is not None else ""


def get_hearing_date(soup) -> str:
    hearing_tag = get_hearing_tag(soup)
    if hearing_tag is None:
        return ""
    date_tag = hearing_tag.parent.find_previous_sibling("th")
    return date_tag.text


def get_hearing_time(soup) -> str:
    hearing_text = get_hearing_text(soup)
    hearing_time_matches = re.search(r"\d{1,2}:\d{2} [AP]M", hearing_text)
    return hearing_time_matches[0] if hearing_time_matches is not None else ""


def get_hearing_officer(soup) -> str:
    hearing_text = get_hearing_text(soup)
    officer_groups = hearing_text.split("Judicial Officer")
    name = officer_groups[1] if len(officer_groups) > 1 else ""
    return name.strip().strip(")")


def get_precinct_number(soup) -> int:
    word_to_number = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

    location_heading = soup.find(text="Location:").parent
    precinct_name = location_heading.find_next_sibling("td").text
    precinct_number = precinct_name.split("Precinct ")[1]

    return word_to_number[precinct_number]


def get_status(status_soup) -> str:
    eviction_tag = status_soup.find(text="Eviction")
    status_tag = eviction_tag.parent.find_next_sibling("div")
    return status_tag.text


def get_register_url(status_soup) -> str:
    link_tag = status_soup.find(style="color: blue")
    relative_link = link_tag.get("href")
    return "https://odysseypa.traviscountytx.gov/JPPublicAccess/" + relative_link


def did_defendant_appear(soup) -> bool:
    """If and only if "appeared" appears, infer defendant apparently appeared."""

    def appeared_in_text(text):
        return text and re.compile("[aA]ppeared").search(text)

    appeared_tag = soup.find(text=appeared_in_text)
    return appeared_tag is not None


def was_defendant_served(soup) -> List[str]:
    dates_of_service = {}
    served_tags = soup.find_all(text="Served")
    for service_tag in served_tags:
        date_tag = service_tag.parent.find_next_sibling("td")
        defendant_tag = service_tag.parent.parent.parent.parent.parent.find_previous_sibling(
            "td"
        )
        dates_of_service[defendant_tag.text] = date_tag.text

    return dates_of_service


def was_defendant_alternative_served(soup) -> List[str]:
    dates_of_service = []
    served_tags = soup.find_all(text="Order Granting Alternative Service")
    for service_tag in served_tags:
        date_tag = service_tag.parent.parent.find_previous_sibling("th")
        dates_of_service.append(date_tag.text)

    return dates_of_service


def make_parsed_hearing(
    soup, status: str = "", register_url: str = ""
) -> Dict[str, str]:
    # TODO handle multiple defendants/plaintiffs with different zips
    disposition_tr = get_disposition_tr_element(soup)
    return {
        "precinct_number": get_precinct_number(soup),
        "style": get_style(soup),
        "plaintiff": get_plaintiff(soup),
        "defendants": get_defendants(soup),
        "case_number": get_case_number(soup),
        "defendant_zip": get_zip(get_defendant_elements(soup)[0]),
        "plaintff_zip": get_zip(get_plaintiff_elements(soup)[0]),
        "hearing_date": get_hearing_date(soup),
        "hearing_time": get_hearing_time(soup),
        "hearing_officer": get_hearing_officer(soup),
        "appeared": did_defendant_appear(soup),
        "status": status,
        "register_url": register_url,
        "disposition_type": get_disposition_type(disposition_tr)
        if disposition_tr is not None
        else "",
        "disposition_amount": get_disposition_amount(disposition_tr)
        if disposition_tr is not None
        else "",
        "disposition_winning_party": get_disposition_winning_party(
            disposition_tr, get_plaintiff(soup)
        )
        if disposition_tr is not None
        else "N/A",
    }


def fetch_parsed_hearing(case_id: str) -> Tuple[str, str]:
    query_result = fetch_page.query_case_id(case_id)
    if query_result is None:
        return None
    result_page, register_page = query_result
    result_soup = BeautifulSoup(result_page, "html.parser")
    register_soup = BeautifulSoup(register_page, "html.parser")

    register_url = get_register_url(result_soup)
    status = get_status(result_soup)
    return make_parsed_hearing(
        soup=register_soup, status=status, register_url=register_url
    )
