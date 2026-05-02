"""KAP API endpoint constants and Pydantic request/response DTOs.

KAP (Kamuyu Aydınlatma Platformu) exposes JSON endpoints under
https://www.kap.org.tr/tr/api/.  These DTOs describe the wire format so
that the rest of the package never has to know raw field names.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.kap.org.tr"
REFERER_URL = f"{BASE_URL}/tr/bildirim-sorgu"

MEMBER_DISCLOSURE_QUERY_URL = f"{BASE_URL}/tr/api/disclosure/members/byCriteria"
FUND_DISCLOSURE_QUERY_URL = f"{BASE_URL}/tr/api/disclosure/funds/byCriteria"
DISCLOSURE_DETAIL_URL = f"{BASE_URL}/tr/Bildirim"  # + /{index}

FUND_LIST_URL = f"{BASE_URL}/tr/api/fund/criteria"  # + /{group}/Y|T
FUND_MEMBERS_URL = f"{BASE_URL}/tr/api/fund/founder"  # + /{group}
COMPANY_ITEMS_URL = f"{BASE_URL}/tr/api/company/items"  # + /{memberType}/A|P
NOTIFICATION_ATTACHMENT_URL = f"{BASE_URL}/tr/api/notification/attachment-detail"  # + /{index}
FILE_DOWNLOAD_URL = f"{BASE_URL}/tr/api/file/download"  # + /{objId}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FundGroup(str, Enum):
    """Fon grubu kodları."""

    BORSA_YATIRIM_FONLARI = "BYF"
    YATIRIM_FONLARI = "YF"
    EMEKLILIK_YATIRIM_FONLARI = "EYF"
    OKS_EMEKLILIK_YATIRIM_FONLARI = "OKS"
    YABANCI_YATIRIM_FONLARI = "YYF"
    VARLIK_FINANSMAN_FONLARI = "VFF"
    KONUT_FINANSMAN_FONLARI = "KFF"
    GAYRIMENKUL_YATIRIM_FONLARI = "GMF"
    GIRISIM_SERMAYESI_FONLARI = "GSF"
    PROJE_FINANSMAN_FONLARI = "PFF"
    TASFIYE_EDILEN_YATIRIM_FONLARI = "TEYF"


class FundSubject(str, Enum):
    """Fon bildirimi konu OID'leri."""

    SORUMLULUK_BEYANI = "4028328d537aad0a015383da38914598"
    ALTI_AYLIK_RAPOR = "8aca490d51458dcf015147f9e6c203f2"
    ARACI_KURUMA_ODENEN_KOMISYON = "8aca490d502dd03b01502dd9c9c60040"
    BIR_SONRAKI_YILA_TAHMINI_TAKIP_FARKI = "4028328d537aad0a015383d773c44584"
    BORSA_DISI_REPO_TERS_REPO = "8aca490d502dd03b01502ddc1678004d"
    BORSA_DISI_SOZLESME_ILKELERI = "8aca490d502dd03b01502decce7600f6"
    BYF_IC_TUZUK = "8aca490d51067d0c0151068012540011"
    FINANSAL_RAPOR = "8aca490d502dd03b01502deede79010a"
    FINANSAL_TABLO_BILDIRIMI = "8aca490d502dd03b01502df05c54011a"
    FON_GIDER_BILGILERI = "8aca490d502dd03b01502dde122c0058"
    FON_KURUCUSUNA_ILISKIN_ACIKLAMA = "8aca490d51058254015105abe3790143"
    FON_SUREKLI_BILGILENDIRME_FORMU = "4028328d53a8d2060153bce347f94a5d"
    FON_TASFIYE_DUYURUSU = "8aca490d502dd03b01502de59b460090"
    FON_TOPLAM_GIDER_ORANI = "4028328d537aad0a015383d09b184552"
    FON_UNVAN_DEGISIKLIGI = "8aca490d51458dcf015147eefdfd031d"
    FONA_ILISKIN_BILGILER = "8aca490d51458dcf015147f7ca3a03b6"
    GENEL_ACIKLAMA = "8aca490d502dd03b01502de6916c009a"
    GERCEKLESEN_TAKIP_FARKI = "4028328d537aad0a015383d991db458e"
    IC_TUZUK = "8aca490d51458dcf015147f57fea039c"
    IHRAC_BELGESI = "8aca490d51458dcf015147feae1f0432"
    IZAHNAME = "8aca490d502dd03b01502deb982000e2"
    KESINLESEN_PORTFOY_BILGILERI = "4028328d537aad0a015383dac84945a2"
    KREDI_DERECELENDIRME_NOTU = "8aca490d51458dcf015147fa9e6903fc"
    OZEL_DURUM_ACIKLAMASI = "8aca490d51458dcf01514802e9ac0490"
    PERFORMANS_SUNUM_RAPORU = "8aca490d502e18ef01502e2efff6006c"
    PORTFOY_DAGILIM_RAPORU = "8aca490d502e34b801502e380044002b"
    TANITIM_FORMU = "4028328d537aad0a015383d60baf4570"
    TUREV_ARAC_ILKELERI = "8aca490d502e34b801502e375fac0021"
    YATIRIM_FONU_BILGI_FORMU = "8aca490d51458dcf015147f333b60361"
    YATIRIMCI_BILGI_FORMU = "8aca490d51153da6015115455c5f00b9"
    YATIRIMCI_RAPORU = "8aca490d51458dcf015147fb9add0406"
    YILLIK_RAPOR = "4028328d537aad0a015383d56e204566"
    YF_IC_TUZUK = "8aca490d502dd03b01502deab28500bc"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class MemberDisclosureQueryBody(BaseModel):
    """Wire-format body for POST /tr/api/disclosure/members/byCriteria."""

    fromDate: str  # "YYYY-MM-DD"
    toDate: str  # "YYYY-MM-DD"
    memberType: str = ""  # "PYS", "YK", "BDK", ...
    mkkMemberOidList: list[str] = []
    inactiveMkkMemberOidList: list[str] = []
    disclosureClass: str = ""
    subjectList: list[str] = []
    isLate: str = ""
    mainSector: str = ""
    sector: str = ""
    subSector: str = ""
    marketOid: str = ""
    index: str = ""
    bdkReview: str = ""
    bdkMemberOidList: list[str] = []
    year: str = ""
    term: str = ""
    ruleType: str = ""
    period: str = ""
    fromSrc: bool = False
    srcCategory: str = ""
    disclosureIndexList: list[int] = []

    model_config = {"populate_by_name": True}


class FundDisclosureQueryBody(BaseModel):
    """Wire-format body for POST /tr/api/disclosure/funds/byCriteria."""

    fromDate: str  # "YYYY-MM-DD"
    toDate: str  # "YYYY-MM-DD"
    fundTypeList: list[str] = []
    mkkMemberOidList: list[str] = []
    fundOidList: list[str] = []
    passiveFundOidList: list[str] = []
    disclosureClass: str = ""
    isLate: str = ""
    subjectList: list[str] = []
    discIndex: list[int] = []
    fromSrc: bool = False
    srcCategory: str = ""

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class DisclosureRow(BaseModel):
    """One row from disclosure/members/byCriteria or disclosure/funds/byCriteria."""

    disclosureIndex: int
    publishDate: str  # "DD.MM.YYYY HH:MM:SS" or ISO
    # Company disclosures
    memberTitle: str | None = None
    # Fund disclosures
    fundCode: str | None = None  # "THF", "AFA", …
    kapTitle: str | None = None  # full fund/company title
    summary: str | None = None  # bildirim özeti
    year: int | None = None
    ruleType: str | None = None  # "11. Ay"
    period: int | None = None
    attachmentCount: int | None = None
    # Common fields
    stockCodes: str | None = None  # "THYAO" — comma-separated
    subject: str | None = None
    disclosureType: str | None = None  # "FS", "DG", "FR", …
    disclosureClass: str | None = None
    disclosureCategory: str | None = None
    hasAttachment: bool | None = None
    isLate: bool | None = None
    isCorrective: bool | None = None
    isEnglish: bool | None = None
    hasMultiLanguageSupport: bool | None = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("hasAttachment", "isLate", "isCorrective", "isEnglish", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool | None:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().upper() in {"TRUE", "1", "EVET", "Y"}
        return bool(v)

    @field_validator("disclosureIndex", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        return int(v)


class CompanyRow(BaseModel):
    """One row from /tr/api/fund/{group}/{status} or /tr/api/fundMembers/{group}."""

    memberOid: str | None = None
    memberTitle: str | None = None
    stockCodes: str | None = None
    memberGroup: str | None = None

    model_config = {"extra": "allow", "populate_by_name": True}


class FundRow(BaseModel):
    """One row from /tr/api/fund/{group}/{status}."""

    fundCode: str | None = None
    fundTitle: str | None = None
    oid: str | None = None
    fundType: str | None = None
    isActive: bool | None = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("isActive", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool | None:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().upper() in {"TRUE", "1", "EVET", "Y", "ACTIVE"}
        return bool(v)
