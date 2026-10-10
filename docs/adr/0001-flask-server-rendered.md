# ADR 0001 – Flask with server-rendered Jinja templates

**Status:** accepted (Sprint 1)

## Context
The brief expects at least a terminal application; the professor allows going
further provided every technology can be explained. The interface must work
offline, on Windows and Linux, in three languages, for one developer.

## Options
| | Flask | FastAPI | Django | Standard library `http.server` |
|---|---|---|---|---|
| Hidden machinery to explain | Low | Medium (async, Pydantic, dependency injection) | High (ORM, admin, middleware) | None, but sessions, CSRF and parsing would be hand-made |
| HTML pages | Native (Jinja2) | Secondary | Native | Manual |
| Lets our own layers stay visible | Yes | Yes | No: Django models want to be the domain | Yes |

A separate JavaScript front end (React, Vue) was rejected: it doubles the
languages to defend and needs a build chain.

## Decision
Flask 3 + Jinja2 templates, one hand-written CSS file, no JavaScript framework.
Extensions limited to Flask-WTF (CSRF only) and Flask-Babel (translations).
Production server: Waitress, because Gunicorn does not run on Windows.

## Consequences
The whole request cycle can be explained in a few minutes. Login, sessions and
access control are our own code, so they must be well tested (they are).
