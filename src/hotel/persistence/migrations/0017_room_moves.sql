-- Sprint 6 (story 6.5): moving a guest to another room during the stay.
-- The room they left stays on the reservation (its nights are still billed),
-- marked with the first night they no longer spent there. NULL = current room.
ALTER TABLE reservation_room ADD COLUMN moved_out_on TEXT;
