# Test evidence: requirement → test

Every rule and scenario of the brief, and every important design decision,
is proved by at least one automated test. Paths are relative to `tests/`;
run one with, for example,
`python -m pytest "tests/integration/test_booking.py::test_capacity_rule"`.

The whole suite runs on every push in GitHub Actions, on Ubuntu and
Windows, with Python 3.11 and 3.13. The Docker image and the Windows
program are built and started by CI too. Coverage must stay ≥ 90 %
(currently 98 %).

## Scenarios of the brief (§4)

| Brief | Scenario | Tests |
|---|---|---|
| §4.1 | Room 204 closed for maintenance for three days | `integration/test_room_service.py::test_scenario_4_1_maintenance_blocks_the_period`, `integration/test_booking.py::test_maintenance_blocks_bookings`, `e2e/test_room_pages.py::test_maintenance_through_the_pages` |
| §4.2 | A returning guest is found, not duplicated | `integration/test_guest_service.py::test_scenario_4_2_returning_guest_is_flagged`, `integration/test_guest_service.py::test_same_document_is_refused`, `e2e/test_guest_pages.py::test_validation_and_duplicates` |
| §4.3 | 10–15 July requested, room booked 12–14 July | `integration/test_booking.py::test_scenario_4_3_conflict_is_refused_with_alternatives`, `e2e/test_booking_pages.py::test_conflict_shows_alternatives` |
| §4.4 | Extend a stay from 3 to 5 nights | `integration/test_change_and_cancel.py::test_scenario_4_4_extend_from_three_to_five_nights` |
| §4.5 | Check-in, then check-out with the final statement | `integration/test_front_desk.py::test_scenario_4_5_check_in`, `integration/test_check_out_and_invoices.py::test_scenario_4_5_check_out_issues_the_final_invoice`, `e2e/test_check_out_pages.py::test_check_out_flow_and_invoice_page` |
| §4.6 | 4 nights, 3 breakfasts, 1 airport transfer | `integration/test_extras_and_settings.py::test_scenario_4_6_breakfasts_and_an_airport_transfer` |
| §4.7 | 3 × 150 DT, 80 DT services, 100 DT deposit | `unit/test_billing.py::test_scenario_4_7_three_nights_services_and_a_deposit`, `unit/test_billing.py::test_scenario_4_7_with_tunisian_style_taxes`, `integration/test_billing.py::test_scenario_4_7_end_to_end` |
| §4.8 | Management statistics | `integration/test_reports.py::test_activity_counts`, `integration/test_reports.py::test_occupancy_excludes_maintenance`, `integration/test_reports.py::test_revenue_counts_when_invoiced_and_cash_separately`, `integration/test_reports.py::test_availability_by_category`, `integration/test_reports.py::test_outstanding_balances`, `e2e/test_report_pages.py::test_reports_page_shows_the_figures` |

## Business rules (requirements.md §4)

| Rule | Tests |
|---|---|
| BR1 unique room number | `integration/test_room_service.py::test_room_numbers_are_unique`, `unit/test_rooms.py::test_room_numbers_are_normalised` |
| BR2 identifiable guests | `integration/test_guest_service.py::test_same_document_is_refused`, `integration/test_guest_service.py::test_update_cannot_steal_another_document`, `unit/test_guests.py::test_documents` |
| BR3 no overlapping reservations | `integration/test_booking.py::test_scenario_4_3_conflict_is_refused_with_alternatives`, `integration/test_booking.py::test_two_receptionists_book_the_same_room_at_the_same_time`, `integration/test_booking.py::test_the_database_guard_becomes_a_clean_conflict` |
| BR4 departure after arrival | `unit/test_period.py::test_a_stay_overlaps_itself_and_counts_its_nights`, `integration/test_booking.py::test_dates_and_notes_are_validated` |
| BR5 maintenance blocks bookings | `integration/test_booking.py::test_maintenance_blocks_bookings`, `integration/test_room_service.py::test_the_database_itself_refuses_a_double_block`, `integration/test_grid_and_guards.py::test_maintenance_over_a_booking_is_refused` |
| BR6 confirmed only with an available room | `integration/test_booking.py::test_out_of_service_and_unknown_rooms`, `integration/test_booking.py::test_availability_search` |
| BR7 occupants ≤ capacity | `unit/test_rooms.py::test_room_capacity_rule`, `integration/test_booking.py::test_capacity_rule`, `integration/test_grid_and_guards.py::test_capacity_cannot_drop_below_a_booking` |
| BR8 cost = nights × rates | `unit/test_reservation_rules.py::test_accommodation_total_is_the_sum_of_locked_nights`, `integration/test_booking.py::test_quote_matches_the_booking` |
| BR9 services on the final bill | `integration/test_extras_and_settings.py::test_scenario_4_6_breakfasts_and_an_airport_transfer`, `unit/test_billing.py::test_voided_charges_are_not_billed` |
| BR10 deposit before arrival | `unit/test_billing.py::test_deposit_before_arrival_payment_afterwards`, `e2e/test_bill_pages.py::test_bill_preview_and_deposit` |
| BR11 20 % fee under 48 h | `unit/test_reservation_rules.py::test_fee_boundaries`, `integration/test_change_and_cancel.py::test_late_cancellation_fee_through_the_service`, `integration/test_billing.py::test_cancellation_fee_is_taken_from_the_deposit_and_the_rest_refunded` |
| BR12 invalid operations explained | `unit/test_domain_basics.py::test_errors_carry_codes_and_params_not_sentences`, `e2e/test_booking_pages.py::test_invalid_bookings_are_explained`, `e2e/test_preferences.py::test_translated_error_messages` |
| BR13 half-open stays | `unit/test_period.py::test_overlap_boundaries`, `unit/test_period.py::test_back_to_back_stays_never_overlap`, `integration/test_booking.py::test_same_day_turnover_is_allowed` |
| BR14 nights = departure − arrival | `unit/test_period.py::test_a_stay_overlaps_itself_and_counts_its_nights` |
| BR15 active statuses block rooms | `unit/test_reservation_rules.py::test_active_statuses` |
| BR16 lifecycle | `unit/test_reservation_rules.py::test_every_transition` |
| BR17 check-in rules | `unit/test_reservation_rules.py::test_check_in_only_from_confirmed`, `unit/test_reservation_rules.py::test_check_in_before_arrival_or_after_the_stay_is_refused`, `integration/test_front_desk.py::test_nobody_moves_in_before_the_previous_guest_has_left` |
| BR18 changes re-check availability | `integration/test_change_and_cancel.py::test_scenario_4_4_extend_from_three_to_five_nights`, `integration/test_change_and_cancel.py::test_shortening_and_capacity_and_versions` |
| BR19 charges only while in the house | `unit/test_extras_taxes_settings.py::test_charges_only_in_the_house_and_within_the_stay`, `integration/test_extras_and_settings.py::test_charges_need_a_guest_in_the_house` |
| BR20 prices locked per night | `integration/test_booking.py::test_create_locks_prices_per_night`, `integration/test_rates.py::test_existing_bookings_keep_their_prices`, `integration/test_change_and_cancel.py::test_kept_nights_keep_their_price_and_new_nights_use_todays_rate` |
| BR21 positive amounts, balance, refunds | `unit/test_billing.py::test_refunds_count_against_payments`, `unit/test_billing.py::test_never_take_more_than_is_owed_or_refund_more_than_was_overpaid`, `integration/test_billing.py::test_payments_never_exceed_the_balance` |
| BR22 issued invoices immutable | `integration/test_check_out_and_invoices.py::test_issued_invoices_never_change`, `integration/test_check_out_and_invoices.py::test_numbers_are_sequential_and_a_failure_leaves_no_gap`, `integration/test_billing.py::test_payments_are_append_only_in_the_database` |
| BR23 derived room status | `integration/test_booking.py::test_room_status_tonight` |
| BR24 integer millimes | `unit/test_money.py::test_floats_and_bools_are_refused`, `unit/test_money.py::test_percent_rounds_half_up`, `unit/test_money.py::test_parse_and_str_round_trip` |
| BR25 search before registering | `integration/test_guest_service.py::test_scenario_4_2_returning_guest_is_flagged`, `unit/test_guests.py::test_search_key_ignores_case_and_accents` |
| BR26 deactivate, never delete | `integration/test_user_service.py::test_deactivation_ends_sessions_immediately`, `integration/test_extras_and_settings.py::test_deactivated_extras_disappear_from_new_charges_only`, `integration/test_anonymisation.py::test_anonymising_erases_personal_data_but_not_invoices` |

## Decisions on ambiguous points (requirements.md §5)

| Decision | Tests |
|---|---|
| Q2 fee details, grace period, 48:00 boundary | `unit/test_reservation_rules.py::test_fee_boundaries`, `unit/test_reservation_rules.py::test_grace_period`, `unit/test_reservation_rules.py::test_cancelling_after_arrival_time_is_refused` |
| Q3 discounts: manager only, capped | `integration/test_billing.py::test_discounts_are_manager_only_capped_and_removable`, `unit/test_billing.py::test_total_discount_is_capped` |
| E maintenance over a booking refused | `integration/test_grid_and_guards.py::test_maintenance_over_a_booking_is_refused` |
| F early departure, no-show | `unit/test_reservation_rules.py::test_early_departure_charges_only_the_nights_stayed`, `integration/test_check_out_and_invoices.py::test_early_departure_releases_the_unused_nights`, `integration/test_front_desk.py::test_no_show_after_the_arrival_time_releases_the_rooms` |
| G taxes | `unit/test_extras_taxes_settings.py::test_percentage_tax_rounds_half_up_to_the_millime`, `unit/test_extras_taxes_settings.py::test_per_adult_night_tax`, `integration/test_billing.py::test_active_tax_rules_are_on_the_bill` |
| H occupancy excludes maintenance | `integration/test_reports.py::test_occupancy_excludes_maintenance`, `integration/test_front_desk.py::test_occupancy_excludes_rooms_under_maintenance` |

## Sprint 6 stories

| Story | Tests |
|---|---|
| 6.1 two-factor sign-in | `unit/test_totp.py::test_totp_matches_rfc_6238_appendix_b`, `unit/test_totp.py::test_codes_from_the_neighbouring_steps_are_accepted_once`, `integration/test_two_factor.py::test_a_code_cannot_be_used_twice`, `integration/test_two_factor.py::test_each_recovery_code_works_once`, `e2e/test_two_factor_pages.py::test_managers_are_reminded_then_blocked_after_the_grace_period` |
| 6.2 Docker | `e2e/test_health.py::test_health_is_public_and_says_little`, plus the CI job "Docker image" (build, uid 10001, healthy, `/login`, CLI inside) |
| 6.3 JSON API | `e2e/test_api.py::test_a_browser_session_is_not_enough`, `e2e/test_api.py::test_calls_are_rate_limited_per_manager`, `integration/test_api_tokens.py::test_a_token_is_shown_once_and_stored_hashed` |
| 6.4 Windows program | `e2e/test_windows_launcher.py::test_first_double_click_creates_the_manager_then_starts`, plus the CI job "Windows executable" (build, start, `/health`, login page) |
| 6.5 room move | `integration/test_room_move.py::test_mid_stay_move_keeps_the_nights_spent_and_the_prices`, `integration/test_room_move.py::test_check_out_after_a_move_dirties_only_the_current_room`, `e2e/test_room_move_pages.py::test_move_from_the_reservation_page` |
| 6.6 hardening | `e2e/test_cookies_over_https.py::test_every_cookie_gets_the_host_prefix_behind_https`, `e2e/test_cookies_over_https.py::test_signing_out_clears_cached_pages` |

## Non-functional requirements (requirements.md §6)

| Requirement | Evidence |
|---|---|
| Layered architecture | `unit/test_architecture.py::test_layer_does_not_import_forbidden_modules` |
| Atomic transactions | `integration/test_database.py::test_unit_of_work_rolls_back_everything_on_error`, `integration/test_booking.py::test_a_failed_booking_leaves_no_trace_and_no_gap` |
| Backups and integrity | `integration/test_backups.py::test_backup_is_a_consistent_verified_copy`, `integration/test_database.py::test_corrupted_database_is_refused` |
| Deny-by-default access | `e2e/test_route_policy.py::test_every_route_declares_an_access_policy`, `e2e/test_route_policy.py::test_a_route_without_policy_is_refused` |
| Audit log | `unit/test_audit_chain.py::test_recomputing_one_hash_is_not_enough_to_hide_an_edit`, `integration/test_audit_log.py::test_database_refuses_updates_and_deletes` |
| Three languages, right-to-left | `e2e/test_translations.py::test_every_source_string_is_translated`, `e2e/test_preferences.py::test_arabic_switches_the_page_to_right_to_left`, `unit/test_charts.py::test_time_runs_right_to_left_in_rtl` |
| Security headers | `e2e/test_route_policy.py::test_security_headers_on_every_page` |
| Windows and Linux | CI matrix (Ubuntu and Windows × Python 3.11 and 3.13) |
| Browsers, real Windows PC, accessibility | Manual: [manual-checks.md](manual-checks.md) |
| Security standard | [asvs.md](asvs.md) (OWASP ASVS 5.0 Level 1) |
