"""Service layer: one class per group of use cases.

Services coordinate the domain and the repositories inside a UnitOfWork. They
know nothing about HTTP or HTML, so the same services are used by the web
interface, the command line and the tests.
"""
