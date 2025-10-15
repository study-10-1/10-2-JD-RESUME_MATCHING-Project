"""add_unique_index_for_jobs

Revision ID: eb2d17db17c3
Revises: ad5da92d3a14
Create Date: 2025-10-14 06:53:55.105209

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb2d17db17c3'
down_revision: Union[str, None] = 'ad5da92d3a14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. UNIQUE INDEX 생성 (중복 방지)
    op.create_index(
        'idx_job_unique',
        'job_posting',
        ['source', 'external_id'],
        unique=True,
        postgresql_where=sa.text('external_id IS NOT NULL')
    )
    
    # 2. 만료 공고 자동 비활성화 트리거
    op.execute("""
        CREATE OR REPLACE FUNCTION deactivate_expired_jobs()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.expires_at IS NOT NULL AND NEW.expires_at < CURRENT_DATE THEN
                NEW.is_active := FALSE;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_deactivate_expired
        BEFORE INSERT OR UPDATE ON job_posting
        FOR EACH ROW
        EXECUTE FUNCTION deactivate_expired_jobs();
    """)


def downgrade() -> None:
    # 트리거 삭제
    op.execute("DROP TRIGGER IF EXISTS trigger_deactivate_expired ON job_posting")
    op.execute("DROP FUNCTION IF EXISTS deactivate_expired_jobs()")
    
    # 인덱스 삭제
    op.drop_index('idx_job_unique', table_name='job_posting')

