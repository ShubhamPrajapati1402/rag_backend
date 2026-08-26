import os
from app.db.session import SessionLocal
from app.models.document import DocumentChunk, Document, DocumentStatus
from zoneinfo import ZoneInfo
from datetime import datetime

db = SessionLocal()
try:
    # 1. Clear DB
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()
    
    # 2. Insert dummy doc
    doc = Document(
        filename="test.pdf",
        file_hash="123",
        config_hash="456",
        status=DocumentStatus.NEW
    )
    db.add(doc)
    db.commit()
    
    doc_id = doc.id
    print(f"Doc ID: {doc_id}")
    
    # 3. Simulate persist_batch
    db_records = []
    for i in range(32, 64):
        db_records.append(DocumentChunk(
            document_id=doc_id,
            page_number=1,
            chunk_index=i,
            text_content=f"Chunk {i}",
            metadata_json={"i": i},
            embedding=[0.0] * 1024
        ))
        
    db.add_all(db_records)
    
    # 4. Trigger flush and update
    db.query(Document).filter(Document.id == doc_id).update({
        Document.updated_at: datetime.now(ZoneInfo("Asia/Kolkata"))
    })
    
    db.commit()
    print("SUCCESS: Inserted 32 chunks.")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    db.close()
