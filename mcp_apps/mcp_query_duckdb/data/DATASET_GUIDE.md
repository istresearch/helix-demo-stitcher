# Multi-Region Demo System - Option 1 Implementation

## Overview

This  datasets are generated dynamically when the demo starts, not stored as pre-built DuckDB files.

## Directory Structure

```
demo/
├── startup_demo.sh                    # Modified to build datasets
├── assets/
│   ├── csv_to_duckdb.py              # Shared CSV importer utility
│   ├── databases/
│   │   ├── .gitignore                # Ignore generated .duckdb files
│   │   └── (generated on startup)
│   └── datasets/
│       ├── hormuz/
│       │   ├── gen_hormuz_data.py
│       │   ├── README_GENERATION.md
│       │   └── config.yaml
│       ├── caribbean/
│       │   ├── gen_caribbean_data.py
│       │   └── config.yaml
│       ├── ukraine/
│       │   ├── gen_ukraine_data.py
│       │   └── config.yaml
│       ├── south_china_sea/
│       │   ├── gen_south_china_sea_data.py
│       │   └── config.yaml
│       └── narcotic_sources/
│           ├── gen_narcotic_sources_data.py
│           └── config.yaml
```

## How It Works

### 1. Startup Flow

```bash
./startup_demo.sh
```

The `startup_demo.sh` script now:
1. ✅ Validates prerequisites (Docker, Git, config files)
2. ✅ **Builds the dataset** (NEW)
   - Checks if database exists
   - If not, runs the generator for the active dataset
   - Imports CSVs to DuckDB using csv_to_duckdb.py
3. ✅ Exports `ACTIVE_DATASET` and `DB_PATH` environment variables
4. ✅ Continues with normal startup (fetch projects, build images, start services)

### 2. Selecting a Dataset

```bash
# Use default (hormuz)
./startup_demo.sh

# Use specific dataset
DEMO_DATASET=caribbean ./startup_demo.sh

# Rebuild (regenerate data even if database exists)
REBUILD_DATA=true DEMO_DATASET=ukraine ./startup_demo.sh
```

### 3. MCP Server Integration

The `ACTIVE_DATASET` and `DB_PATH` environment variables are available to services:

```yaml
# docker-compose.yml
services:
  mcp-query-duckdb:
    environment:
      - ACTIVE_DATASET=${ACTIVE_DATASET}
      - DB_PATH=${DB_PATH}
    volumes:
      - ${DB_PATH}:/app/data/active.duckdb:ro
```

Then in your MCP service:

```python
# mcp_apps/mcp_query_duckdb/config.py
import os
import duckdb

class Config:
    ACTIVE_DATASET = os.getenv("ACTIVE_DATASET", "hormuz")
    DB_PATH = os.getenv("DB_PATH") or f"./assets/databases/{ACTIVE_DATASET}.duckdb"
    
    @classmethod
    def get_connection(cls):
        return duckdb.connect(cls.DB_PATH)
```

## Connected Network Data

All datasets are generated with **internal network connectivity** to support relationship and graph analysis:

### Features
- **~5% Internal Calls**: Each dataset contains approximately 5% of phone calls where the called number is another phone number that exists in the same dataset
- **Reproducible Graphs**: Using the same seed value will generate identical connection patterns
- **Multi-Hop Analysis**: Enables queries like "find all numbers that are 3 hops from phone X" (A calls B who calls C who calls A)

### Use Cases
✅ Network topology discovery  
✅ Phone tree analysis  
✅ Communication graph visualization  
✅ Call chain tracing (A→B→C→D)  
✅ Loop detection (cyclic calls)  
✅ Relationship mapping  

### Example Query
```sql
-- Find all numbers that call each other (direct connections)
SELECT DISTINCT 
    a.callingNumber as from_number,
    a.calledNumber as to_number
FROM cdr a
WHERE a.calledNumber IN (
    SELECT DISTINCT callingNumber FROM cdr
)
LIMIT 10;
```

### Example Multi-Hop Query
```sql
-- Find 2-hop connections (A calls B, B calls C)
WITH first_hop AS (
    SELECT DISTINCT 
        a.callingNumber as caller,
        a.calledNumber as first_recipient
    FROM cdr a
    WHERE a.calledNumber IN (SELECT DISTINCT callingNumber FROM cdr)
)
SELECT DISTINCT
    fh.caller,
    fh.first_recipient,
    c.calledNumber as second_recipient
FROM first_hop fh
JOIN cdr c ON fh.first_recipient = c.callingNumber
WHERE c.calledNumber IN (SELECT DISTINCT callingNumber FROM cdr)

## Available Datasets

### 1. Hormuz (Default)
```bash
DEMO_DATASET=hormuz ./startup_demo.sh
```
- **Location**: Strait of Hormuz (Iran, UAE, Oman)
- **Records**: ~300 CDR, ~450-600 MAID
- **Focus**: Middle Eastern telecom

### 2. Caribbean
```bash
DEMO_DATASET=caribbean ./startup_demo.sh
```
- **Location**: Caribbean Sea (Cuba, Jamaica, Haiti, Dominican Republic, Puerto Rico)
- **Records**: ~500 CDR, ~750-1000 MAID
- **Focus**: Maritime communications

### 3. Ukraine
```bash
DEMO_DATASET=ukraine ./startup_demo.sh
```
- **Location**: Eastern Europe
- **Records**: ~100 CDR, ~150-300 MAID
- **Focus**: Regional telecom

### 4. South China Sea
```bash
DEMO_DATASET=south_china_sea ./startup_demo.sh
```
- **Location**: Southeast Asia (Vietnam, Philippines, Thailand, Singapore, Malaysia)
- **Records**: ~500 CDR, ~750-1000 MAID
- **Focus**: Maritime and regional communications

### 5. Narcotic Sources
```bash
DEMO_DATASET=narcotic_sources ./startup_demo.sh
```
- **Location**: Global (Colombia, Mexico, Afghanistan, Peru, Myanmar, Bolivia)
- **Records**: ~600 CDR, ~900-1200 MAID
- **Focus**: Narcotic trafficking network analysis and communication patterns

## Adding New Datasets

### Step 1: Create Directory Structure
```bash
mkdir -p demo/assets/datasets/[new_region]
```

### Step 2: Create Generator
```bash
cp demo/assets/datasets/caribbean/gen_caribbean_data.py \
   demo/assets/datasets/[new_region]/gen_[new_region]_data.py
```

Then customize:
- Update `CountryConfig` with region-specific settings
- Adjust class name (e.g., `CaribeanDataGenerator` → `NewRegionDataGenerator`)
- Customize phone prefixes, MCC codes, coordinates, operators

### Step 3: Create Config File
```yaml
# demo/assets/datasets/[new_region]/config.yaml
dataset:
  name: new_region
  description: New Region - Telecommunications Data
  region: Geographic region
  countries:
    - Country1
    - Country2
  
generation:
  cdr_count_per_country: 100
  seed: 42
```

### Step 4: Test
```bash
DEMO_DATASET=new_region ./startup_demo.sh
```

## Customization Points

### Generate Different Data Volumes
```bash
# Generate 200 CDR records per country instead of 100
cd demo/assets/datasets/caribbean
python gen_caribbean_data.py --count 200 --seed 42 --db ../../databases/caribbean.duckdb
```

### Use Custom Seeds for Reproducibility
```bash
DEMO_DATASET=caribbean SEED=12345 ./startup_demo.sh
# Or directly
python gen_caribbean_data.py --seed 12345 --db caribbean.duckdb
```

### Manual Dataset Building
```bash
# Build without full startup
cd demo/assets/datasets/hormuz
python gen_hormuz_data.py --db ../../databases/hormuz.duckdb

# Or use CSV importer directly on existing CSVs
cd demo/assets/datasets/caribbean
python ../../csv_to_duckdb.py --directory . --db ../../databases/caribbean.duckdb
```

## Git Workflow

**Tracked in Git:**
- ✅ Data generators (`gen_*.py`)
- ✅ Configuration files (`config.yaml`)
- ✅ Dataset documentation
- ✅ `startup_demo.sh` script

**NOT tracked in Git (see `.gitignore`):**
- ❌ Generated `.duckdb` files
- ❌ Generated CSV files
- ❌ Generated `.parquet` files

```bash
# Git status shows clean (despite generated files)
git status
# On branch main
# nothing to commit, working tree clean
```

## Docker Integration

### In docker-compose.yml
```yaml
version: '3.8'

services:
  mcp-query-duckdb:
    environment:
      - ACTIVE_DATASET=${ACTIVE_DATASET:-hormuz}
      - DB_PATH=${DB_PATH:-/app/demo/assets/databases/hormuz.duckdb}
    volumes:
      - ./demo/assets/databases:/app/databases:ro
```

### Build on Startup with Hook
```yaml
  mcp-query-duckdb:
    command: >
      bash -c "
        python /app/startup_datasets.py &&
        python -m mcp_server
      "
```

## Troubleshooting

### Dataset not building
```bash
# Check if generator exists
ls demo/assets/datasets/[name]/gen_[name]_data.py

# Run generator manually
cd demo/assets/datasets/[name]
python gen_[name]_data.py --db ../../databases/[name].duckdb
```

### Database not found by MCP service
```bash
# Check DB path
echo $DB_PATH

# Verify database exists
ls -lh demo/assets/databases/*.duckdb

# Test DuckDB connection
python -c "import duckdb; conn = duckdb.connect('$DB_PATH'); print(conn.query('SELECT * FROM cdr LIMIT 1'))"
```

### Switching datasets mid-development
```bash
# Rebuild with new dataset
REBUILD_DATA=true DEMO_DATASET=new_dataset ./startup_demo.sh
```

## Performance Notes

- **First Run**: ~10-30 seconds to generate datasets (depends on record count)
- **Subsequent Runs**: Instant (reuses cached database)
- **Rebuild**: ~10-30 seconds (with `REBUILD_DATA=true`)
- **Database Size**: ~5-50MB per dataset (compressed DuckDB)

## Benefits of Option 1

✅ **Reproducibility** - Regenerate exact same data with `--seed`  
✅ **Version Control** - Generators tracked in Git  
✅ **Small Footprint** - No large binary files in repo  
✅ **Flexibility** - Easy to add new regions  
✅ **Isolation** - Each dataset completely independent  
✅ **Testing** - Generate fresh data for each test run  

## Next Steps

1. **Test the setup**:
   ```bash
   ./startup_demo.sh
   # Should see dataset being built
   ```

2. **Integrate with MCP server**:
   - Read `$ACTIVE_DATASET` and `$DB_PATH` from environment
   - Mount database volume in docker-compose.yml

3. **Add more regions**:
   - Copy a generator template
   - Customize country configs
   - Add to startup script

4. **Optimize if needed**:
   - Cache pre-built databases in artifact storage
   - Generate incrementally with `--append`
   - Pre-generate common datasets in CI/CD

