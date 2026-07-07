**Unreleased**

* - Fixed summary field mappings to match legacy connector behavior:
  * - `list_objects` and `list_tickets` now include `view_names` field when listing available views
  * - `update_object` and `update_ticket` now return `obj_id` in summary
  * - All other action behaviour is preserved and output is identical
