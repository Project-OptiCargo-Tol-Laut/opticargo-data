from opticargo_data.db import ColumnInfo, apply_schema_defaults, project_row, validate_required_columns
from opticargo_data.io import load
from opticargo_data.normalize import prepare_seed_rows


def col(name, data_type='character varying', udt='varchar', nullable=False, default=None):
    return ColumnInfo(name, data_type, udt, nullable, default, False)


def test_cargo_listing_live_schema_is_fully_covered():
    source = {name: load(name) for name in [
        'users','ports','commodities','routes','ships','suppliers','voyages',
        'cargo_capacities','cargo_listings','bookings'
    ]}
    prepared, _ = prepare_seed_rows(source)
    row = prepared['cargo_listings'][0]
    cols = {
        'supplier_id': col('supplier_id','uuid','uuid'),
        'commodity_id': col('commodity_id','uuid','uuid'),
        'volume_ton': col('volume_ton','numeric','numeric'),
        'volume_m3': col('volume_m3','numeric','numeric',True),
        'available_from': col('available_from','date','date'),
        'available_until': col('available_until','date','date'),
        'origin_port_id': col('origin_port_id','uuid','uuid'),
        'destination_port_id': col('destination_port_id','uuid','uuid'),
        'asking_price_per_ton': col('asking_price_per_ton','numeric','numeric'),
        'status': col('status'),
        'certifications': col('certifications','json','json'),
        'cargo_type': col('cargo_type',nullable=True),
        'version': col('version','integer','int4'),
        'id': col('id','uuid','uuid'),
        'created_at': col('created_at','timestamp with time zone','timestamptz',default='CURRENT_TIMESTAMP'),
        'updated_at': col('updated_at','timestamp with time zone','timestamptz',default='CURRENT_TIMESTAMP'),
    }
    projected = apply_schema_defaults('cargo_listings', project_row('cargo_listings', row, cols), cols)
    validate_required_columns('cargo_listings', projected, cols)
    assert projected['certifications']
    assert projected['cargo_type'] in {'general','dry_food','frozen'}
    assert projected['version'] == 1


def test_booking_live_schema_is_fully_covered():
    source = {name: load(name) for name in [
        'users','ports','commodities','routes','ships','suppliers','voyages',
        'cargo_capacities','cargo_listings','bookings'
    ]}
    prepared, _ = prepare_seed_rows(source)
    row = prepared['bookings'][0]
    cols = {
        'voyage_id': col('voyage_id','uuid','uuid'),
        'cargo_listing_id': col('cargo_listing_id','uuid','uuid'),
        'recommendation_id': col('recommendation_id','uuid','uuid',True),
        'booked_volume_ton': col('booked_volume_ton','numeric','numeric'),
        'booked_volume_m3': col('booked_volume_m3','numeric','numeric',True),
        'agreed_price_per_ton': col('agreed_price_per_ton','numeric','numeric'),
        'status': col('status'),
        'booking_date': col('booking_date','timestamp with time zone','timestamptz',default='CURRENT_TIMESTAMP'),
        'confirmation_date': col('confirmation_date','timestamp with time zone','timestamptz',True),
        'booking_ref': col('booking_ref'),
        'created_by': col('created_by','uuid','uuid'),
        'cancelled_reason': col('cancelled_reason','text','text',True),
        'version': col('version','integer','int4'),
        'id': col('id','uuid','uuid'),
        'created_at': col('created_at','timestamp with time zone','timestamptz',default='CURRENT_TIMESTAMP'),
        'updated_at': col('updated_at','timestamp with time zone','timestamptz',default='CURRENT_TIMESTAMP'),
    }
    projected = apply_schema_defaults('bookings', project_row('bookings', row, cols), cols)
    validate_required_columns('bookings', projected, cols)
    assert projected['created_by']
    assert projected['booking_ref'].startswith('OCG-DEMO-')
    assert projected['version'] == 1


def test_all_live_gateway_required_columns_are_covered():
    source = {name: load(name) for name in [
        'users','ports','commodities','routes','ships','suppliers','voyages',
        'cargo_capacities','cargo_listings','bookings'
    ]}
    prepared, _ = prepare_seed_rows(source)

    # Snapshot distilled from the user's successful --schema-only report. Only
    # required/no-default columns need listing here; timestamp DB defaults are
    # intentionally omitted.
    required = {
        'users': {
            'username': ('character varying','varchar'), 'email': ('character varying','varchar'),
            'role': ('character varying','varchar'), 'account_status': ('character varying','varchar'),
            'password_hash': ('character varying','varchar'), 'id': ('uuid','uuid'),
        },
        'ports': {
            'name': ('character varying','varchar'), 'city': ('character varying','varchar'),
            'province': ('character varying','varchar'), 'latitude': ('numeric','numeric'),
            'longitude': ('numeric','numeric'), 'facilities': ('json','json'),
            'operating_hours': ('json','json'), 'id': ('uuid','uuid'),
        },
        'commodities': {
            'name': ('character varying','varchar'), 'category': ('character varying','varchar'),
            'special_requirements': ('json','json'), 'is_perishable': ('boolean','bool'),
            'certifications_required': ('json','json'), 'id': ('uuid','uuid'),
        },
        'routes': {
            'origin_port_id': ('uuid','uuid'), 'destination_port_id': ('uuid','uuid'),
            'distance_nm': ('numeric','numeric'), 'estimated_days': ('integer','int4'),
            'route_type': ('character varying','varchar'), 'is_active': ('boolean','bool'),
            'id': ('uuid','uuid'),
        },
        'ships': {
            'name': ('character varying','varchar'), 'imo_number': ('character varying','varchar'),
            'ship_type': ('character varying','varchar'), 'gross_tonnage': ('numeric','numeric'),
            'deadweight_tonnage': ('numeric','numeric'), 'cargo_capacity_m3': ('numeric','numeric'),
            'operator_id': ('uuid','uuid'), 'certifications': ('json','json'),
            'status': ('character varying','varchar'), 'id': ('uuid','uuid'),
        },
        'suppliers': {
            'user_id': ('uuid','uuid'), 'business_name': ('character varying','varchar'),
            'port_id': ('uuid','uuid'), 'commodity_ids': ('json','json'),
            'avg_monthly_volume_ton': ('numeric','numeric'), 'rating': ('numeric','numeric'),
            'verified': ('boolean','bool'), 'id': ('uuid','uuid'),
        },
        'voyages': {
            'ship_id': ('uuid','uuid'), 'route_id': ('uuid','uuid'),
            'departure_date': ('timestamp with time zone','timestamptz'),
            'arrival_date': ('timestamp with time zone','timestamptz'),
            'total_capacity_ton': ('numeric','numeric'), 'used_capacity_ton': ('numeric','numeric'),
            'remaining_capacity_ton': ('numeric','numeric'), 'status': ('character varying','varchar'),
            'waypoints': ('json','json'), 'version': ('integer','int4'), 'id': ('uuid','uuid'),
        },
        'cargo_capacities': {
            'voyage_id': ('uuid','uuid'), 'available_weight_ton': ('numeric','numeric'),
            'available_volume_m3': ('numeric','numeric'), 'cargo_type_allowed': ('json','json'),
            'version': ('integer','int4'), 'id': ('uuid','uuid'),
        },
        'cargo_listings': {
            'supplier_id': ('uuid','uuid'), 'commodity_id': ('uuid','uuid'),
            'volume_ton': ('numeric','numeric'), 'available_from': ('date','date'),
            'available_until': ('date','date'), 'origin_port_id': ('uuid','uuid'),
            'destination_port_id': ('uuid','uuid'), 'asking_price_per_ton': ('numeric','numeric'),
            'status': ('character varying','varchar'), 'certifications': ('json','json'),
            'version': ('integer','int4'), 'id': ('uuid','uuid'),
        },
        'bookings': {
            'voyage_id': ('uuid','uuid'), 'cargo_listing_id': ('uuid','uuid'),
            'booked_volume_ton': ('numeric','numeric'), 'agreed_price_per_ton': ('numeric','numeric'),
            'status': ('character varying','varchar'), 'booking_ref': ('character varying','varchar'),
            'created_by': ('uuid','uuid'), 'version': ('integer','int4'), 'id': ('uuid','uuid'),
        },
    }

    for table, columns in required.items():
        cols = {name: col(name, dtype, udt) for name, (dtype, udt) in columns.items()}
        projected = project_row(table, prepared[table][0], cols)
        if table == 'users':
            projected['password_hash'] = '$test-hash'
        projected = apply_schema_defaults(table, projected, cols)
        validate_required_columns(table, projected, cols)
