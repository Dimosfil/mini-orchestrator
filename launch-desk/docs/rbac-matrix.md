# Dental CRM RBAC Matrix

| Role | Patients | Appointments | Treatment Plans | Clinical Notes | Invoices | Billing | Tasks | Users | Dashboard | Jobs |
|---|---|---|---|---|---|---|---|---|---|---|
| owner | rw | rw | rw | rw | rw | rw | rw | rw | rw | rw |
| admin | rw | rw | rw | rw | rw | rw | rw | rw | rw | rw |
| dentist | rw | rw | rw | rw | - | - | r/w tasks | - | r | limited (audit/read) |
| assistant | r | rw | r | r | - | - | r | - | r | - |
| receptionist | rw | rw | - | - | r | w | rw | - | r | - |
| billing | r | - | - | - | rw | rw | r | - | r | - |
| viewer | r | r | r | r | r | r | r | - | r | - |

Legend: `r` read-only, `rw` create/update/delete permitted, `-` no access.
