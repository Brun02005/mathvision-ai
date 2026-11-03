from alembic import context

import database
import models  # noqa: F401  (registers the tables in Base.metadata for autogenerate)

target_metadata = database.Base.metadata

# Same engine (and DATABASE_URL) as the app: no second place to configure the connection
with database.engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things: batch mode rebuilds the table, keeping the data
        render_as_batch=database.IS_SQLITE,
    )
    with context.begin_transaction():
        context.run_migrations()
