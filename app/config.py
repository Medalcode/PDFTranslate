import os
from dotenv import load_dotenv

load_dotenv()

SOURCE_LANG: str = os.getenv("SOURCE_LANG", "en")
TARGET_LANG: str = os.getenv("TARGET_LANG", "es")
UPLOAD_DIR: str  = os.getenv("UPLOAD_DIR", "data/uploads")
OUTPUT_DIR: str  = os.getenv("OUTPUT_DIR", "data/outputs")

# ── LLM Configuration (optional — vastly improves translation quality) ────────
# Provider: "gemini" | "openai" | "custom" (OpenAI-compatible)
LLM_PROVIDER: str  = os.getenv("LLM_PROVIDER", "gemini")
LLM_API_KEY: str   = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str     = os.getenv("LLM_MODEL", "")       # empty = provider default
LLM_BASE_URL: str  = os.getenv("LLM_BASE_URL", "")    # for custom/local endpoints

# ── Protected technical terms ─────────────────────────────────────────────────
# Define here the terms that the translators should skip.
import json
_default_terms = [
    "Hadoop", "HDFS", "YARN", "MapReduce", "Spark", "Hive", "Pig",
    "Flume", "Sqoop", "HBase", "ZooKeeper", "Avro", "Parquet",
    "Oozie", "Tez", "Kafka", "Storm", "Flink", "Cassandra", "MongoDB",
    "Thrift", "Crunch", "Nutch", "AWS", "S3", "EC2", "GCS", "Azure", 
    "Docker", "Kubernetes", "Java", "Python", "Scala", "Ruby", "Maven", 
    "Gradle", "Git", "MRUnit", "Kerberos", "WebHDFS", "HttpFS",
    "JSON", "XML", "CSV", "HTTP", "REST", "JDBC", "ODBC", "SQL",
    "ISBN", "API", "IDE", "GFS", "DAG", "UDF", "UDAF", "IDL",
    "Twitter", "Facebook", "YouTube", "LinkedIn", "GitHub", "Safari",
    "O'Reilly", "Cloudera", "Apache", "Peachpit", "Syngress",
    "US", "UK", "CAN"
]

_env_terms = os.getenv("PROTECTED_TERMS", "")
if _env_terms:
    try:
        PROTECTED_TERMS = set(json.loads(_env_terms))
    except Exception:
        PROTECTED_TERMS = set(_default_terms)
else:
    PROTECTED_TERMS = set(_default_terms)


# Ensure runtime directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
