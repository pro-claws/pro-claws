"""Read-only database inventory shared by source and final restore checks."""
def collect(query):
    tables = query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    result = {"rows": {}, "sequences": {}}
    for (table,) in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        result['rows'][table] = query('SELECT count(*) FROM public.' + quoted)[0][0]
    for (name,) in query("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
        quoted = '"' + name.replace('"', '""') + '"'
        actual = query('SELECT last_value,is_called FROM public.' + quoted)[0]
        result['sequences'][name] = list(actual)
    result['migrations'] = query('SELECT app,name FROM django_migrations ORDER BY app,name')
    result['constraints'] = query("SELECT conrelid::regclass::text,conname,contype,convalidated,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2")
    result['indexes'] = query("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname")
    return result
