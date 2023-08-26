"""empty message

Revision ID: 11bf958a6b13
Revises: 
Create Date: 2023-07-11 09:29:03.198171

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '11bf958a6b13'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('politician', schema=None) as batch_op:
        batch_op.add_column(sa.Column('money', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'state', ['state_id'], ['id'])

    with op.batch_alter_table('primary', schema=None) as batch_op:
        batch_op.alter_column('state_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('primary', schema=None) as batch_op:
        batch_op.alter_column('state_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('politician', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('money')

    # ### end Alembic commands ###
