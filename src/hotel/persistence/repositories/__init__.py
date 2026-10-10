"""Repositories translate between domain objects and table rows.

Every query uses `?` placeholders: values are sent to SQLite separately from
the SQL text, which is what makes SQL injection impossible.
"""
