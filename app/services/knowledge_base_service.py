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
    {
        "source_id": "supervisor_manual_el921_grievance_2015",
        "name": "EL-921 Supervisor Guide to Handling Grievances",
        "source_type": "SUPERVISOR_MANUAL",
        "official_page": None,
        "download_url": None,
        "local_path": (
            "uploads/supervisor_manual/"
            "EL-921 Supervisor Guide to Handling Grievs 04-2015.pdf"
        ),
        "content_type": "application/pdf",
        "version": "2015-04",
        "document_metadata": {
            "manual_code": "EL-921",
            "local_filename": "EL-921 Supervisor Guide to Handling Grievs 04-2015.pdf",
            "corpus": "supervisor_manual",
        },
    },
    {
        "source_id": "supervisor_manual_el801_safety_2020",
        "name": "EL-801 Supervisor's Safety Handbook",
        "source_type": "SUPERVISOR_MANUAL",
        "official_page": None,
        "download_url": None,
        "local_path": (
            "uploads/supervisor_manual/"
            "Handbook-EL-801-Supervisors-Safety-Handbook-July-2020.pdf"
        ),
        "content_type": "application/pdf",
        "version": "2020-07",
        "document_metadata": {
            "manual_code": "EL-801",
            "local_filename": (
                "Handbook-EL-801-Supervisors-Safety-Handbook-July-2020.pdf"
            ),
            "corpus": "supervisor_manual",
        },
    },
    {
        "source_id": "supervisor_manual_f21_time_attendance_2016",
        "name": "F-21 Time and Attendance Handbook",
        "source_type": "SUPERVISOR_MANUAL",
        "official_page": None,
        "download_url": None,
        "local_path": (
            "uploads/supervisor_manual/"
            "Handbook_F-21_Time_and_Attendance_February_2016_reduced2.pdf"
        ),
        "content_type": "application/pdf",
        "version": "2016-02",
        "document_metadata": {
            "manual_code": "F-21",
            "local_filename": (
                "Handbook_F-21_Time_and_Attendance_February_2016_reduced2.pdf"
            ),
            "corpus": "supervisor_manual",
        },
    },
]


class KnowledgeBaseService:
    @staticmethod
    def seed_official_sources(db: Session):
        created = []
        existing = []
        updated = []

        for item in OFFICIAL_SOURCES:
            source = (
                db.query(SourceDocument)
                .filter(SourceDocument.source_id == item["source_id"])
                .first()
            )

            if source:
                existing.append(item["source_id"])
                changed = False
                for field_name in (
                    "name",
                    "source_type",
                    "official_page",
                    "download_url",
                    "local_path",
                    "content_type",
                    "version",
                    "document_metadata",
                ):
                    if field_name not in item:
                        continue
                    value = item[field_name]
                    if getattr(source, field_name) != value:
                        setattr(source, field_name, value)
                        changed = True
                if changed:
                    updated.append(item["source_id"])
                continue

            source = SourceDocument(
                source_id=item["source_id"],
                name=item["name"],
                source_type=item["source_type"],
                official_page=item["official_page"],
                download_url=item["download_url"],
                local_path=item.get("local_path"),
                content_type=item.get("content_type"),
                version=item.get("version"),
                document_metadata=item.get("document_metadata"),
                is_current=True,
            )

            db.add(source)
            created.append(item["source_id"])

        db.commit()

        return {
            "message": "Official knowledge base sources seeded.",
            "created": created,
            "already_existing": existing,
            "updated": updated,
        }