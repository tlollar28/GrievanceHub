from sqlalchemy.orm import Session

from app.database.models import SourceDocument


OFFICIAL_SOURCES = [
    {
        "source_id": "npmhu_national_agreement_2022_2025",
        "name": "NPMHU National Agreement 2022-2025",
        "source_type": "CONTRACT",
        "official_page": "https://m.npmhu.org/resources/2022-national-agreement",
        "download_url": "https://m.npmhu.org/resources/body/2022-2025-NPMHU-National-Agreement.pdf",
    },
    {
        "source_id": "usps_elm_55",
        "name": "USPS Employee and Labor Relations Manual ELM 55",
        "source_type": "ELM",
        "official_page": "https://about.usps.com/manuals/elm/elm.htm",
        "download_url": "https://about.usps.com/manuals/elm/elm55.zip",
    },
    {
        "source_id": "npmhu_cim_v6",
        "name": "NPMHU-USPS Contract Interpretation Manual v6",
        "source_type": "CIM",
        "official_page": "https://m.npmhu.org/resources/contract-interpretation-manual-v-6",
        "download_url": "https://www.npmhu.org/resources/body/CIM-V.6-FINAL-NPMHU.pdf",
    },
    {
        "source_id": "knoxville_lmou_current",
        "name": "Knoxville LMOU",
        "source_type": "LMOU",
        "official_page": None,
        "download_url": None,
    },
]


class KnowledgeBaseService:
    @staticmethod
    def seed_official_sources(db: Session):
        created = []
        existing = []

        for item in OFFICIAL_SOURCES:
            source = (
                db.query(SourceDocument)
                .filter(SourceDocument.source_id == item["source_id"])
                .first()
            )

            if source:
                existing.append(item["source_id"])
                continue

            source = SourceDocument(
                source_id=item["source_id"],
                name=item["name"],
                source_type=item["source_type"],
                official_page=item["official_page"],
                download_url=item["download_url"],
                is_current=True,
            )

            db.add(source)
            created.append(item["source_id"])

        db.commit()

        return {
            "message": "Official knowledge base sources seeded.",
            "created": created,
            "already_existing": existing,
        }