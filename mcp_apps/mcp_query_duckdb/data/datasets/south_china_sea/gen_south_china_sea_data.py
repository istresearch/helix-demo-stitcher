#!/usr/bin/env python3
"""
South China Sea Data Generator

Generates synthetic CDR, MAID, and connection data for the South China Sea region.
Covers maritime and telecommunications in Southeast Asia.

Usage:
    python gen_south_china_sea_data.py --count 100 --seed 42 --db south_china_sea.duckdb
"""

import csv
import random
import argparse
import sys
import os
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import uuid


class CountryConfig:
    """Configuration for South China Sea region countries."""

    CONFIGS = {
        'Vietnam': {
            'phone_prefix': '+84',
            'lat_range': (8.5, 23.0),
            'lon_range': (102.0, 109.5),
            'mcc': '452',
            'operators': {
                'Viettel': '01',
                'Mobifone': '02',
                'Vinaphone': '03',
            },
            'locale': 'vi_VN',
        },
        'Philippines': {
            'phone_prefix': '+63',
            'lat_range': (5.0, 19.0),
            'lon_range': (121.0, 128.5),
            'mcc': '515',
            'operators': {
                'Globe': '01',
                'Smart': '02',
                'SUN': '03',
            },
            'locale': 'en_PH',
        },
        'Thailand': {
            'phone_prefix': '+66',
            'lat_range': (5.5, 20.5),
            'lon_range': (97.5, 105.5),
            'mcc': '520',
            'operators': {
                'AIS': '01',
                'DTAC': '02',
                'TrueMove': '03',
            },
            'locale': 'th_TH',
        },
        'Singapore': {
            'phone_prefix': '+65',
            'lat_range': (1.2, 1.5),
            'lon_range': (103.5, 104.1),
            'mcc': '525',
            'operators': {
                'Singtel': '01',
                'StarHub': '02',
                'M1': '03',
            },
            'locale': 'en_SG',
        },
        'Malaysia': {
            'phone_prefix': '+60',
            'lat_range': (1.0, 7.0),
            'lon_range': (99.5, 104.5),
            'mcc': '502',
            'operators': {
                'Celcom': '01',
                'Maxis': '02',
                'U Mobile': '03',
            },
            'locale': 'ms_MY',
        },
    }

    @classmethod
    def get(cls, country):
        if country not in cls.CONFIGS:
            raise ValueError(f"Unknown country: {country}")
        return cls.CONFIGS[country]


class SouthChinaSeaDataGenerator:
    """Generate South China Sea telecommunications data."""

    DEVICE_MAKES = ['Apple', 'Samsung', 'Xiaomi', 'Motorola', 'LG']
    DEVICE_MODELS = {
        'Apple': ['iPhone 14', 'iPhone 13', 'iPhone 12'],
        'Samsung': ['Galaxy S23', 'Galaxy A53', 'Galaxy A52'],
        'Xiaomi': ['Redmi Note 12', 'Mi 12', 'Poco X5'],
        'Motorola': ['Edge 40', 'G72', 'G52'],
        'LG': ['V60', 'G8X'],
    }
    CONNECTION_METHODS = ['4G LTE', '5G', 'WiFi', '3G']
    RECORD_TYPES = ['VOICE', 'SMS', 'DATA']
    RECORD_TYPE_WEIGHTS = [0.6, 0.25, 0.15]

    MAX_LOCATION_VARIANCE_M = 150
    MAX_TIME_VARIANCE_S = 60

    def __init__(self, countries, count=45, seed=None, output_dir='./', db_file=None):
        self.countries = countries
        self.count = count
        self.output_dir = output_dir
        self.db_file = db_file
        self.base_datetime = datetime.strptime('2026-04-03 08:15:23', '%Y-%m-%d %H:%M:%S')

        if seed is not None:
            random.seed(seed)

    def generate_phone_number(self, country):
        config = CountryConfig.get(country)
        prefix = config['phone_prefix']
        if country == 'Cuba':
            suffix = random.randint(1234567, 9999999)
        else:
            suffix = random.randint(2000000, 9999999)
        return f"{prefix}{suffix}"

    def generate_location(self, country):
        config = CountryConfig.get(country)
        lat = random.uniform(*config['lat_range'])
        lon = random.uniform(*config['lon_range'])
        return round(lat, 4), round(lon, 4)

    def generate_operator_info(self, country):
        config = CountryConfig.get(country)
        operator = random.choice(list(config['operators'].keys()))
        mnc = config['operators'][operator]
        return operator, config['mcc'], mnc

    def generate_imsi(self, mcc, mnc):
        return f"{mcc}{mnc}{random.randint(1234567890, 9999999999)}"

    def generate_cell_id(self, country):
        config = CountryConfig.get(country)
        mcc = config['mcc']
        mnc = f"{random.randint(1, len(config['operators'])):02d}"
        lac = f"{random.randint(1000, 9999)}"
        cid = f"{random.randint(5000, 9999)}"
        cgi = f"{mcc}{mnc}{random.randint(1000, 9999)}"
        return cgi, mcc, mnc, lac, cid

    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return c * 6371000

    def add_location_variance(self, lat, lon):
        lat_variance = random.uniform(-self.MAX_LOCATION_VARIANCE_M / 111000,
                                     self.MAX_LOCATION_VARIANCE_M / 111000)
        lon_variance = random.uniform(-self.MAX_LOCATION_VARIANCE_M / 111000,
                                     self.MAX_LOCATION_VARIANCE_M / 111000)
        return round(lat + lat_variance, 4), round(lon + lon_variance, 4)

    def generate_cdr_records(self):
        cdr_records = []
        current_time = self.base_datetime

        # First pass: Generate all phone numbers that will be calling
        all_phone_numbers = []
        for country in self.countries:
            for _ in range(self.count // len(self.countries)):
                all_phone_numbers.append(self.generate_phone_number(country))

        # Second pass: Generate CDR records with ~5% internal calls
        phone_number_index = 0
        internal_call_threshold = max(1, int(len(all_phone_numbers) * 0.05))
        internal_calls_created = 0

        for country in self.countries:
            for _ in range(self.count // len(self.countries)):
                current_time += timedelta(seconds=random.randint(30, 600))

                calling_number = all_phone_numbers[phone_number_index]
                phone_number_index += 1

                # Create internal calls for ~5% of records
                if internal_calls_created < internal_call_threshold and len(all_phone_numbers) > 1:
                    called_number = random.choice(all_phone_numbers)
                    internal_calls_created += 1
                else:
                    called_country = random.choice(self.countries + ['International'])
                    called_number = self.generate_phone_number(called_country) if called_country != 'International' else f"+{random.randint(1, 999)}{random.randint(1000000, 9999999)}"

                operator, mcc, mnc = self.generate_operator_info(country)
                imsi = self.generate_imsi(mcc, mnc)

                lat, lon = self.generate_location(country)
                cgi, mcc, mnc, lac, cid = self.generate_cell_id(country)

                record_type = random.choices(self.RECORD_TYPES, weights=self.RECORD_TYPE_WEIGHTS)[0]

                cdr_records.append({
                    'callingNumber': calling_number,
                    'calledNumber': called_number,
                    'IMSI': imsi,
                    'eventTime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'recordType': record_type,
                    'LAT': lat,
                    'LON': lon,
                    'CGI': cgi,
                    'MCC': mcc,
                    'MNC': mnc,
                    'LAC': lac,
                    'CID': cid,
                    'country': country,
                    'dt': current_time,
                })

        return cdr_records

    def generate_maid_records(self, cdr_records):
        maid_records = []

        for cdr_record in cdr_records:
            num_maids = random.randint(1, 3)

            for _ in range(num_maids):
                time_offset = timedelta(seconds=random.randint(-self.MAX_TIME_VARIANCE_S, self.MAX_TIME_VARIANCE_S))
                maid_time = cdr_record['dt'] + time_offset

                maid_lat, maid_lon = self.add_location_variance(cdr_record['LAT'], cdr_record['LON'])

                device_make = random.choice(self.DEVICE_MAKES)
                device_model = random.choice(self.DEVICE_MODELS[device_make])
                device_os = 'iOS' if device_make == 'Apple' else 'Android'

                os_version = random.choice(['16.5', '17.0']) if device_os == 'iOS' else random.choice(['12', '13', '14'])

                rsrp = random.randint(-140, -90)
                rsrq = random.randint(-20, -3)
                rssnr = random.randint(-10, 20)
                dbm = rsrp
                cqi = random.randint(1, 15)

                config = CountryConfig.get(cdr_record['country'])

                maid_records.append({
                    'ID': str(uuid.uuid4()).upper(),
                    'ID_TYPE': 'AAID' if device_os == 'Android' else 'IDFA',
                    'TIMESTAMP': maid_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'LATITUDE': maid_lat,
                    'LONGITUDE': maid_lon,
                    'ALTITUDE': f"{random.randint(0, 100)}",
                    'HORIZONTAL_ACCURACY': f"{random.randint(5, 50)}",
                    'VERTICAL_ACCURACY': f"{random.randint(5, 30)}",
                    'SPEED': f"{random.randint(0, 50)}",
                    'COURSE': f"{random.randint(0, 360)}",
                    'HEADING': f"{random.randint(0, 360)}",
                    'DEVICE_MAKE': device_make,
                    'DEVICE_MODEL': device_model,
                    'DEVICE_OS': device_os,
                    'DEVICE_OS_VERSION': os_version,
                    'CONNECTION_METHOD': random.choice(self.CONNECTION_METHODS),
                    'OPERATOR_NAME': random.choice(list(config['operators'].keys())),
                    'CELL_IDENTITY': cdr_record['CID'],
                    'IP_ADDRESS': f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}",
                    'GEOHASH': self.generate_geohash(maid_lat, maid_lon),
                    'DERIVED_COUNTRY': cdr_record['country'],
                    'USER_LOCALE': config['locale'],
                    'GATEWAY_LATITUDE': cdr_record['LAT'],
                    'GATEWAY_LONGITUDE': cdr_record['LON'],
                    'DBM': str(dbm),
                    'RSRP': str(rsrp),
                    'RSRQ': str(rsrq),
                    'RSSNR': str(rssnr),
                    'CQI': str(cqi),
                    'FLOOR': str(random.randint(0, 20)) if random.random() > 0.5 else '',
                    'FOREGROUND': random.choice(['true', 'false', 'true']),
                    'dt': maid_time,
                })

        return maid_records

    @staticmethod
    def generate_geohash(lat, lon):
        lat_char = chr(ord('A') + int((lat + 90) / 2))
        lon_char = chr(ord('A') + int((lon + 180) / 3.6))
        return lat_char + lon_char + str(random.randint(1000, 9999))

    def calculate_confidence(self, distance_m, time_delta_s, rsrp_dbm=None):
        MAX_DISTANCE = 1000
        MAX_TIME = 180

        if distance_m > MAX_DISTANCE or time_delta_s > MAX_TIME:
            return None

        distance_score = 1.0 - (distance_m / MAX_DISTANCE)
        time_score = 1.0 - (abs(time_delta_s) / MAX_TIME)

        signal_bonus = 0.0
        if rsrp_dbm is not None:
            signal_score = (-90 - rsrp_dbm) / (-90 - (-140))
            signal_score = max(0, min(1, signal_score))
            signal_bonus = signal_score * 0.2

        confidence_score = distance_score * 0.5 + time_score * 0.3 + signal_bonus * 0.2

        if confidence_score >= 0.7:
            return 'high'
        elif confidence_score >= 0.4:
            return 'medium'
        else:
            return 'low'

    def generate_connections(self, cdr_records, maid_records):
        connections = []

        for maid_record in maid_records:
            for cdr_record in cdr_records:
                distance_m = self.haversine_distance(
                    maid_record['LATITUDE'], maid_record['LONGITUDE'],
                    cdr_record['LAT'], cdr_record['LON']
                )

                time_delta = abs((maid_record['dt'] - cdr_record['dt']).total_seconds())

                confidence = self.calculate_confidence(
                    distance_m, time_delta,
                    rsrp_dbm=int(maid_record['RSRP'])
                )

                if confidence is not None:
                    connections.append({
                        'maid_id': maid_record['ID'],
                        'phone_number': cdr_record['callingNumber'],
                        'distance': round(distance_m, 2),
                        'maid_timestamp': maid_record['TIMESTAMP'],
                        'cdr_timestamp': cdr_record['eventTime'],
                        'confidence': confidence,
                    })

        return connections

    def save_csv(self, data, filename, fieldnames):
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            print(f"✓ Saved {len(data)} records to {filename}")
            return True
        except IOError as e:
            print(f"✗ Error writing {filename}: {e}", file=sys.stderr)
            return False

    def import_to_duckdb(self):
        """Import to DuckDB using csv_to_duckdb."""
        if not self.db_file:
            return True

        try:
            import subprocess
            script_dir = os.path.dirname(os.path.abspath(__file__))
            assets_dir = os.path.dirname(os.path.dirname(script_dir))
            importer_script = os.path.join(assets_dir, 'csv_to_duckdb.py')

            if not os.path.exists(importer_script):
                print(f"⚠ csv_to_duckdb.py not found")
                return False

            output_dir_abs = os.path.abspath(self.output_dir)
            db_file_abs = os.path.join(output_dir_abs, self.db_file)

            cmd = [sys.executable, importer_script, '--directory', output_dir_abs, '--db', db_file_abs]

            print(f"\nImporting CSVs to DuckDB...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            return result.returncode == 0

        except Exception as e:
            print(f"✗ Error importing to DuckDB: {e}", file=sys.stderr)
            return False

    def generate_all(self):
        print(f"Generating data for: {', '.join(self.countries)}\n")

        os.makedirs(self.output_dir, exist_ok=True)

        print("Generating CDR records...")
        cdr_records = self.generate_cdr_records()
        cdr_fieldnames = ['callingNumber', 'calledNumber', 'IMSI', 'eventTime', 'recordType', 'LAT', 'LON', 'CGI', 'MCC', 'MNC', 'LAC', 'CID']
        self.save_csv([{k: v for k, v in r.items() if k in cdr_fieldnames} for r in cdr_records], 'cdr.csv', cdr_fieldnames)

        print("Generating MAID records...")
        maid_records = self.generate_maid_records(cdr_records)
        maid_fieldnames = ['ID', 'ID_TYPE', 'TIMESTAMP', 'LATITUDE', 'LONGITUDE', 'ALTITUDE', 'HORIZONTAL_ACCURACY', 'VERTICAL_ACCURACY', 'SPEED', 'COURSE', 'HEADING', 'DEVICE_MAKE', 'DEVICE_MODEL', 'DEVICE_OS', 'DEVICE_OS_VERSION', 'CONNECTION_METHOD', 'OPERATOR_NAME', 'CELL_IDENTITY', 'IP_ADDRESS', 'GEOHASH', 'DERIVED_COUNTRY', 'USER_LOCALE', 'GATEWAY_LATITUDE', 'GATEWAY_LONGITUDE', 'DBM', 'RSRP', 'RSRQ', 'RSSNR', 'CQI', 'FLOOR', 'FOREGROUND']
        self.save_csv([{k: v for k, v in r.items() if k in maid_fieldnames} for r in maid_records], 'maid.csv', maid_fieldnames)

        print("Generating connections...")
        connections = self.generate_connections(cdr_records, maid_records)
        connection_fieldnames = ['maid_id', 'phone_number', 'distance', 'maid_timestamp', 'cdr_timestamp', 'confidence']
        self.save_csv(connections, 'connections_with_confidence.csv', connection_fieldnames)

        if self.db_file:
            self.import_to_duckdb()

        print(f"\nSummary:")
        print(f"  CDR records:  {len(cdr_records)}")
        print(f"  MAID records: {len(maid_records)}")
        print(f"  Connections: {len(connections)}")


def main():
    parser = argparse.ArgumentParser(description='Generate South China Sea telecommunications data')
    parser.add_argument('--countries', nargs='+', default=['Vietnam', 'Philippines', 'Thailand', 'Singapore', 'Malaysia'],
                       choices=['Vietnam', 'Philippines', 'Thailand', 'Singapore', 'Malaysia'],
                       help='Countries to generate data for')
    parser.add_argument('--count', type=int, default=45, help='CDR records per country')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    parser.add_argument('--output-dir', type=str, default='./generated/', help='Output directory')
    parser.add_argument('--db', type=str, default=None, help='DuckDB database file')

    args = parser.parse_args()

    generator = SouthChinaSeaDataGenerator(
        countries=args.countries,
        count=args.count,
        seed=args.seed,
        output_dir=args.output_dir,
        db_file=args.db
    )

    generator.generate_all()
    return 0


if __name__ == '__main__':
    sys.exit(main())

