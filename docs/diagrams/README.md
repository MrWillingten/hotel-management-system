# UML diagrams

One [draw.io](https://app.diagrams.net) file per diagram: open it at
app.diagrams.net (*File → Open from → Device*, or drag the file onto the page)
or in the draw.io desktop app. Every shape stays editable. *File → Export as →
PDF / PNG / SVG* gives the picture for the report.

| File | Diagram |
|---|---|
| [use-cases-front-desk.drawio](use-cases-front-desk.drawio) | Use cases 1/2: front desk (Receptionist; the Manager inherits all of it; authenticator app) |
| [use-cases-management.drawio](use-cases-management.drawio) | Use cases 2/2: management, the server operator (command line) and other programs (JSON API) |
| [classes-domain-stays.drawio](classes-domain-stays.drawio) | Classes 1/2: stays, rooms, guests and money |
| [classes-domain-accounts.drawio](classes-domain-accounts.drawio) | Classes 2/2: accounts, security, audit and support |
| [classes-architecture.drawio](classes-architecture.drawio) | Architecture: layers and their classes |

## Where the content comes from

* **Use cases**: the pages of the application and the role checks of the
  services (authorization matrix in [../security.md](../security.md#authorization-matrix)).
  Lines from an actor end on the side of the use case facing it, so none
  crosses another use case.
* **Classes**: attributes, types, enumeration values and operations were read
  from the source code (Python's `ast` module) on 19 Oct 2026, then laid out
  with Graphviz. Relationships and multiplicities come from the identifiers
  the classes hold (`guest_id`, `room_id`...) and the lists they own
  (`rooms`, `nights`...). After a change in `src/hotel/domain/`, update the
  class by hand in draw.io.

Notation: «stereotype», `/name` derived attribute (a Python property),
*italics* abstract class, ◆ composition, ◇ aggregation, ▷ generalisation,
dashed arrow dependency («include», «extend», «use»...), numbers at line
ends multiplicities.
