from pathlib import Path

MAIN_DOC_URL = 'https://docs.python.org/3/'
"""Ссылка на документацию Python 3."""

BASE_DIR = Path(__file__).parent
"""Базовая директория."""

DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S'
"""Шаблон для формата даты, для логирования."""

MAIN_DOC_PEP_URL = 'https://peps.python.org/'
"""Ссылка на перечень PEP."""

EXPECTED_STATUS = {
    'A': ('Active', 'Accepted'),
    'D': ('Deferred',),
    'F': ('Final',),
    'P': ('Provisional',),
    'R': ('Rejected',),
    'S': ('Superseded',),
    'W': ('Withdrawn',),
    '': ('Draft', 'Active'),
}
"""Ожидаемый статус PEP."""

PATTERN_NUMBER_OF_PEP = r'(?P<number_of_pep>^\d+$)'
"""Шаблон для поиска номера PEP."""
