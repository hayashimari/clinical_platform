import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.resource import Resource
from app.models.resource_segment import ResourceSegment

db: Session = SessionLocal()

with open("data/anesthesia/raw.json") as f:
    lines = f.readlines()

for line in lines:
    data = json.loads(line)

    title = data.get("title")
    abstract = data.get("elocationid", "")

    resource = Resource(
        title=title,
        resource_type="paper",
        abstract=abstract,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{data.get('uid')}/"
    )
    db.add(resource)
    db.flush()

    segment = ResourceSegment(
        resource_id=resource.id,
        segment_index=0,
        content=title + " " + abstract
    )
    db.add(segment)

db.commit()
db.close()