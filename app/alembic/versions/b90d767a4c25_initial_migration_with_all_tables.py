"""Initial migration with all tables

Revision ID: b90d767a4c25
Revises: 
Create Date: 2025-09-27 14:47:20.593499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b90d767a4c25'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create packages table
    op.create_table('packages',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('data_limit', sa.Integer(), nullable=True),
        sa.Column('price', sa.DECIMAL(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True, default='TZS'),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_packages_id', 'packages', ['id'])
    
    # Create accounts table
    op.create_table('accounts',
        sa.Column('id', UUID(as_uuid=True), nullable=False, primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('mobile_number', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mobile_number')
    )
    op.create_index('ix_accounts_id', 'accounts', ['id'])
    op.create_index('ix_accounts_mobile_number', 'accounts', ['mobile_number'])
    
    # Create vouchers table
    op.create_table('vouchers',
        sa.Column('id', UUID(as_uuid=True), nullable=False, primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('account_id', UUID(as_uuid=True), nullable=True),
        sa.Column('package_id', sa.String(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('data_limit', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['package_id'], ['packages.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_vouchers_id', 'vouchers', ['id'])
    op.create_index('ix_vouchers_code', 'vouchers', ['code'])
    
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', UUID(as_uuid=True), nullable=False, primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', UUID(as_uuid=True), nullable=True),
        sa.Column('voucher_id', UUID(as_uuid=True), nullable=True),
        sa.Column('package_id', sa.String(), nullable=True),
        sa.Column('amount', sa.DECIMAL(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('transaction_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['voucher_id'], ['vouchers.id']),
        sa.ForeignKeyConstraint(['package_id'], ['packages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transactions_id', 'transactions', ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order to handle foreign key constraints
    op.drop_table('transactions')
    op.drop_table('vouchers')
    op.drop_table('accounts')
    op.drop_table('packages')
