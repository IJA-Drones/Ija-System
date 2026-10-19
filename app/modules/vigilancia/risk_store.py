"""Persistência de agregados e parâmetros, isolada por prefeitura e demonstração."""
import hashlib
import json
import time
import uuid
import sqlalchemy as sa
from .field_store import FieldStore, FieldStoreError
from .risk_models import RiscoAnalise
from .risk import _text


class RiskStore(FieldStore):
    def save(self, report, *, prefeitura, demo, actor, fonte):
        fonte = _text(fonte, "Fonte e recorte do histórico", 200)
        digest = hashlib.sha256(json.dumps({"report":report,"fonte":fonte}, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        table = RiscoAnalise.__table__
        with self.connection(write_prefeitura=prefeitura) as conn:
            existing=conn.scalar(sa.select(table.c.id).where(table.c.prefeitura==prefeitura,table.c.demo==demo,table.c.digest==digest))
            if existing:
                return existing
            count=conn.scalar(sa.select(sa.func.count()).select_from(table).where(table.c.prefeitura==prefeitura,table.c.demo==demo))
            if count >= 100:
                raise FieldStoreError("Limite de 100 análises por prefeitura e tipo de dado. Solicite manutenção.")
            identifier=uuid.uuid4().hex
            conn.execute(table.insert().values(id=identifier,prefeitura=prefeitura,demo=demo,actor=str(actor),fonte=fonte,criado=time.time(),digest=digest,report=report))
            return identifier

    def history(self, prefeitura, demo):
        table=RiscoAnalise.__table__
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sa.select(table.c.id,table.c.fonte,table.c.criado).where(table.c.prefeitura==prefeitura,table.c.demo==demo).order_by(table.c.criado.desc()).limit(100)).mappings()]

    def get(self, identifier, prefeitura, demo):
        table=RiscoAnalise.__table__
        with self.connection() as conn:
            row=conn.execute(sa.select(table).where(table.c.id==identifier,table.c.prefeitura==prefeitura,table.c.demo==demo)).mappings().first()
            return dict(row) if row else None
