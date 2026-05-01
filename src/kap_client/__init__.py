"""kap_client — Python client for https://www.kap.org.tr.

Public API
----------
:class:`Kap`
    Main entry point.  Use as a context manager.

:class:`Disclosure`
    A single KAP public disclosure.

:class:`Attachment`
    A file attached to a disclosure.

:class:`Company`
    A KAP-registered company.

:class:`Fund`
    A KAP-registered investment fund.

:class:`FundGroup`
    Enum of fund group codes (``BYF``, ``YF``, ``EYF``, …).

:class:`FundSubject`
    Enum of fund disclosure subject OIDs.

Exceptions
----------
:class:`KapError`
:class:`RateLimitError`
:class:`EmptyResponseError`
:class:`CompanyNotFoundError`
"""

from ._endpoints import FundGroup, FundSubject
from ._kap import Kap
from ._models import Attachment, Company, Disclosure, Fund
from .exceptions import CompanyNotFoundError, EmptyResponseError, KapError, RateLimitError

__all__ = [
    "Kap",
    "Disclosure",
    "Attachment",
    "Company",
    "Fund",
    "FundGroup",
    "FundSubject",
    "KapError",
    "RateLimitError",
    "EmptyResponseError",
    "CompanyNotFoundError",
]
