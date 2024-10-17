import re
import requests_cache
import logging

from bs4 import BeautifulSoup
from tqdm import tqdm

from urllib.parse import urljoin
from constants import BASE_DIR, MAIN_DOC_URL, MAIN_DOC_PEP_URL, EXPECTED_STATUS
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import get_response, find_tag


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    # session = requests_cache.CachedSession()
    # response = session.get(whats_new_url)
    # response.encoding = 'utf-8'
    response = get_response(session, whats_new_url)
    if response is None:
        # Если основная страница не загрузится, программа закончит работу.
        return
    soup = BeautifulSoup(response.text, features='lxml')
    # main_div = soup.find('section', attrs={'id': 'what-s-new-in-python'})
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    # div_with_ul = main_div.find('div', attrs={'class': 'toctree-wrapper'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        # response = session.get(version_link)
        # response.encoding = 'utf-8'
        response = get_response(session, version_link)
        if response is None:
            # Если страница не загрузится, программа перейдёт к следующей ссылке.
            continue 
        soup = BeautifulSoup(response.text, 'lxml')
        # h1 = soup.find('h1')
        h1 = find_tag(soup, 'h1')
        dl = soup.find('dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )

    # for row in results:
    #     print(*row)
    return results


def latest_versions(session):
    # session = requests_cache.CachedSession()
    # response = session.get(MAIN_DOC_URL)
    # response.encoding = 'utf-8'
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = soup.find('div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Не найден список c версиями Python')

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

    # for row in results:
    #     print(*row)
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    # session = requests_cache.CachedSession()
    # response = session.get(downloads_url)
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_tag = soup.find('div', {'role': 'main'})
    table_tag = main_tag.find('table', {'class': 'docutils'})
    pdf_a4_tag = table_tag.find('a', {'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    print(filename)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def find_mismatched_pep(session, pattern_number_of_pep, results_card_page, statuses):
    response = get_response(session, MAIN_DOC_PEP_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    tags_on_the_main_page = soup.find_all('td')
    results_for_main_page = []
    pattern_key_for_status_pep = r'(?P<key_for_status_pep>^(\S{1,2})?$)'
    for tag in tags_on_the_main_page:
        text_match = re.search(pattern_key_for_status_pep, tag.text)
        if text_match and re.search(
            pattern_number_of_pep, tag.find_next('td').text
        ):
            results_for_main_page.append(text_match.group(
                'key_for_status_pep')
            )
    count = 0
    for keys, res in zip(results_for_main_page, statuses):
        if res not in EXPECTED_STATUS[keys[1:]]:
            logging.info(f'Несовпадающие статусы:\n'
                         f'{results_card_page[count]}\n'
                         f'Статус в карточке: {statuses[count]}\n'
                         f'Ожидаемые статусы: {EXPECTED_STATUS[keys[1:]]}\n')
        count += 1


def pep(session):
    results = [('Статус', 'Количество')]
    response = get_response(session, MAIN_DOC_PEP_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    find_all_tags = soup.find_all('a', {'class': 'pep reference internal'})
    results_card_page = []
    pattern_number_of_pep = r'(?P<number_of_pep>^\d+$)'
    for tag in find_all_tags:
        text_match = re.search(pattern_number_of_pep, tag.text)
        if text_match:
            short_link = tag['href']
            full_url = urljoin(MAIN_DOC_PEP_URL, short_link)
            results_card_page.append(full_url)
    statuses = []
    for pep_url in results_card_page:
        response = get_response(session, pep_url)
        if response is None:
            return
        soup = BeautifulSoup(response.text, 'lxml')

        find_tag = soup.find('dt', {'class': ['field-even', 'field-odd']})

        while find_tag and find_tag.text != 'Status:':
            find_tag = find_tag.find_next_sibling(
                'dt', {'class': ['field-even', 'field-odd']}
            )
        statuses.append(find_tag.find_next_sibling('dd').text)

    unique_statuses = set(statuses)
    count_statuses = []
    for unique_status in unique_statuses:
        count_statuses.append((unique_status, statuses.count(unique_status)))
        results.append((unique_status, statuses.count(unique_status)))
    results.append(('Total', len(statuses)))
    find_mismatched_pep(
        session, pattern_number_of_pep, results_card_page, statuses
    )
    # response = get_response(session, MAIN_DOC_PEP_URL)
    # if response is None:
    #     return
    # soup = BeautifulSoup(response.text, 'lxml')
    # tags_on_the_main_page = soup.find_all('td')
    # results_for_main_page = []
    # pattern_key_for_status_pep = r'(?P<key_for_status_pep>^(\S{1,2})?$)'
    # for tag in tags_on_the_main_page:
    #     text_match = re.search(pattern_key_for_status_pep, tag.text)
    #     if text_match and re.search(
    #         pattern_number_of_pep, tag.find_next('td').text
    #     ):
    #         results_for_main_page.append(text_match.group(
    #             'key_for_status_pep')
    #         )
    # count = 0
    # for keys, res in zip(results_for_main_page, statuses):
    #     if res not in EXPECTED_STATUS[keys[1:]]:
    #         logging.info(f'Несовпадающие статусы:\n'
    #                      f'{results_card_page[count]}\n'
    #                      f'Статус в карточке: {statuses[count]}\n'
    #                      f'Ожидаемые статусы: {EXPECTED_STATUS[keys[1:]]}\n')
    #     count += 1
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    # Запускаем функцию с конфигурацией логов.
    configure_logging()
    # Отмечаем в логах момент запуска программы.
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    # Логируем переданные аргументы командной строки.
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    # Логируем завершение работы парсера.
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
