```mermaid
erDiagram
  USERS {
    int id PK
    string name
    string role_scopes
  }
  HORSES {
    int id PK
    string name
    string notes
  }
  SESSIONS {
    int id PK
    int horse_id FK
    string surface
    string notes
    datetime started_at
    datetime stopped_at
    string status
  }
  SENSOR_READINGS {
    int id PK
    int session_id FK
    bigint ts_ms
    double ax
    double ay
    double az
    double gx
    double gy
    double gz
  }
  FEATURE_WINDOWS {
    int id PK
    int session_id FK
    bigint ts_start
    bigint ts_end
    double cadence_spm
    double stride_var
    double asymmetry_proxy
    double energy
  }
  ANOMALIES {
    int id PK
    int window_id FK UNIQUE
    string method
    double score
    string severity
  }
  BASELINES {
    int id PK
    int horse_id FK
    string feature_name
    double median
    double mad
    datetime updated_at
  }

  HORSES ||--o{ SESSIONS : has
  SESSIONS ||--o{ SENSOR_READINGS : contains
  SESSIONS ||--o{ FEATURE_WINDOWS : produces
  FEATURE_WINDOWS ||--o| ANOMALIES : may_trigger
```