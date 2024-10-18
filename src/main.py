import logging
import re
from urllib.parse import urljoin
from collections import defaultdict

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import (BASE_DIR, EXPECTED_STATUS, MAIN_DOC_PEP_URL,
                       MAIN_DOC_URL,
                       PATTERN_NUMBER_OF_PEP)
from outputs import control_output
from utils import find_tag, get_response
from exceptions import ListOfPythonVersionException


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )
    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')

    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise ListOfPythonVersionException('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_tag = find_tag(soup, 'div', attrs={'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', attrs={'href': re.compile(r'.+pdf-a4\.zip$')}
    )

    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    dict_results = defaultdict(int)
    results = [('Статус', 'Количество')]
    response = get_response(session, MAIN_DOC_PEP_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    find_all_tags = soup.find_all('td')
    key_of_statuses = []
    results_card_page = []
    for tag in find_all_tags:
        text_match = re.search(PATTERN_NUMBER_OF_PEP, tag.text)
        if text_match:
            short_link = tag.find('a')['href']
            full_url = urljoin(MAIN_DOC_PEP_URL, short_link)
            key_of_statuses.append(tag.find_previous_sibling('td').text)
            results_card_page.append(full_url)

    statuses = []
    for pep_url in tqdm(results_card_page):
        response = get_response(session, pep_url)
        if response is None:
            return
        soup = BeautifulSoup(response.text, 'lxml')
        find_tag_dt = find_tag(
            soup, 'dt', attrs={'class': ['field-even', 'field-odd']}
        )

        while find_tag_dt and find_tag_dt.text != 'Status:':
            find_tag_dt = find_tag_dt.find_next_sibling(
                'dt', {'class': ['field-even', 'field-odd']}
            )

        dict_results[find_tag_dt.find_next_sibling('dd').text] += 1
        statuses.append(find_tag_dt.find_next_sibling('dd').text)
    for keys, res in zip(key_of_statuses, statuses):
        if res not in EXPECTED_STATUS[keys[1:]]:
            logging.info(
                f'Несовпадающие статусы:\n'
                f'{results_card_page[statuses.index(res)]}\n'
                f'Статус в карточке: {statuses[statuses.index(res)]}\n'
                f'Ожидаемые статусы: {EXPECTED_STATUS[keys[1:]]}\n'
            )
    results.extend(dict_results.items())
    results.append(('Total', sum(dict_results.values())))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
