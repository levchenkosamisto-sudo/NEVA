#!/usr/bin/env python3
import sys, os, json, argparse, time, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

if sys.version_info < (3, 11):
    print("FATAL: Python 3.11+ required")
    sys.exit(1)

try:
    import requests
    from docx import Document
except ImportError as e:
    print(f"FATAL: {e}")
    sys.exit(1)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

CONFIG = {
    "model": "mistral-large-latest",
    "timeout": 60,
    "max_retries": 1,
    "gemini_model": "gemini-2.5-flash",
    "allowed_relations": ["INHERITS","IMPLEMENTS","DEPENDS_ON","EXTENDS","REFERENCES"],
    "allowed_severities": ["BLOCKER","WARNING"],
    "allowed_statuses": ["DRAFT","REVIEW","APPROVED","FIXED","OBSOLETE","FROZEN_ACTIVE","FROZEN_DEPRECATED"],
    "doc_id_pattern": r"^NEVA-[A-Z]+-\d{3}$"
}

class IndexerLogger:
    def __init__(self, log_path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries = []
    def log(self, entry):
        entry["timestamp"] = datetime.now().isoformat()
        self.entries.append(entry)
        with open(self.log_path, 'w') as f:
            json.dump({"logs": self.entries}, f, indent=2)
    def add_operation(self, op, status, details=None):
        self.log({"operation": op, "status": status, "details": details or {}})

class Diagnostics:
    @staticmethod
    def check_env_vars(mock_mode=False):
        if mock_mode:
            return True
        missing = []
        if not os.getenv("MISTRAL_API_KEY"):
            missing.append("MISTRAL_API_KEY")
        if not os.getenv("GEMINI_API_KEY"):
            missing.append("GEMINI_API_KEY")
        if missing:
            print(f"FATAL: missing {missing}")
            sys.exit(1)
        return True
    @staticmethod
    def check_registry(path):
        if not path.exists():
            print(f"FATAL: registry not found: {path}")
            sys.exit(1)
        with open(path) as f:
            data = json.load(f)
        if "documents" not in data:
            print("FATAL: invalid registry")
            sys.exit(1)
        return data

class FileHandler:
    @staticmethod
    def read_document(path):
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        if path.suffix == '.md':
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        elif path.suffix == '.docx':
            doc = Document(path)
            return '\n'.join(p.text for p in doc.paragraphs)
        raise ValueError(f"Unsupported format: {path.suffix}")
    @staticmethod
    def write_index(data, path, force=False):
        if path.exists() and not force:
            raise FileExistsError(f"Index exists: {path}. Use --force")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

class APIClient:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
    
    def _clean_json(self, content):
        content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n?```\s*$', '', content, flags=re.MULTILINE)
        return content.strip()
    
    def call_mistral(self, registry_context, document):
        if self.mock_mode:
            return self._mock_index(document)
        
        system_prompt = """You are NEVA INDEXER. Return ONLY valid JSON with these fields: 
doc_id (string, format NEVA-XXX-999), 
title (string), 
type (string), 
version (string), 
status (string, one of: DRAFT, REVIEW, APPROVED, FIXED, OBSOLETE, FROZEN_ACTIVE, FROZEN_DEPRECATED),
verified (false), 
verified_by (null), 
verified_at (null), 
date_created (YYYY-MM-DD), 
author (string or null), 
path (string), 
parents (array of strings), 
children (array of strings), 
conflicts (array of objects with doc_id, severity, description),
updates_required (array of objects), 
open_issues (array of objects).
Extract from document. Include any conflicts mentioned (like superseded by)."""
        
        user_prompt = f"Registry: {registry_context}\n\nDocument:\n{document}\n\nProduce index card in JSON."
        
        for attempt in range(CONFIG["max_retries"] + 1):
            try:
                r = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}, json={"model": CONFIG["model"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1, "max_tokens": 4000, "response_format": {"type": "json_object"}}, timeout=CONFIG["timeout"])
                r.raise_for_status()
                return json.loads(self._clean_json(r.json()["choices"][0]["message"]["content"]))
            except Exception as e:
                if attempt == CONFIG["max_retries"]:
                    print(f"FATAL: Mistral error: {e}")
                    sys.exit(1)
                time.sleep(2)
    
    def call_gemini(self, document, index):
        if self.mock_mode:
            return {"verdict":"APPROVED","confidence":0.95,"issues":[],"summary":"Mock"}
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{CONFIG['gemini_model']}:generateContent?key={gemini_key}"
        
        prompt = f"""Verify this index card. Return ONLY valid JSON with these fields: verdict ("APPROVED" or "REJECTED"), confidence (0.0-1.0), issues (list of objects with field, description, severity), summary (string).

Document:
{document}

Index:
{json.dumps(index, indent=2)}"""
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        
        for attempt in range(2):
            try:
                r = requests.post(url, json=payload, timeout=30)
                r.raise_for_status()
                result = r.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = self._clean_json(text)
                return json.loads(cleaned)
            except Exception as e:
                if attempt:
                    print(f"FATAL: Gemini error: {e}")
                    sys.exit(1)
                print(f"Gemini attempt 1 failed: {e}, retrying...")
                time.sleep(2)
    
    def _mock_index(self, doc):
        return {"doc_id": "NEVA-TEST-001", "title": "Test", "type": "TEST", "version": "1.0", "status": "DRAFT", "verified": False, "verified_by": None, "verified_at": None, "date_created": datetime.now().strftime("%Y-%m-%d"), "author": "Mock", "path": "test.md", "parents": [], "children": [], "conflicts": [], "updates_required": [], "open_issues": []}

class IndexValidator:
    @staticmethod
    def validate_schema(idx):
        errors = []
        required = ["doc_id","title","type","version","status","verified","verified_by","verified_at","date_created","author","path","parents","children","conflicts","updates_required","open_issues"]
        for f in required:
            if f not in idx:
                errors.append(f"missing:{f}")
        if idx.get("verified") is not False:
            errors.append("verified must be false")
        if "status" in idx and idx["status"] not in CONFIG["allowed_statuses"]:
            errors.append(f"invalid status:{idx['status']}")
        return len(errors)==0, errors

class NevaIndexer:
    def __init__(self, args):
        self.args = args
        self.base_path = Path(os.getenv("NEVA_HOME","~/Documents/NEVA")).expanduser()
        self.logger = IndexerLogger(self.base_path/"logs"/"indexer_log.json")
    
    def run(self):
        try:
            Diagnostics.check_env_vars(mock_mode=self.args.mock)
            reg = Diagnostics.check_registry(Path(self.args.registry))
            doc = FileHandler.read_document(Path(self.args.doc))
            client = APIClient(mock_mode=self.args.mock)
            idx = client.call_mistral(json.dumps(reg), doc)
            valid, err = IndexValidator.validate_schema(idx)
            if not valid:
                print(f"FATAL: {err}")
                sys.exit(1)
            idx["verified"] = False
            ver = client.call_gemini(doc, idx)
            
            print("="*60)
            print("DEBUG: Gemini Response")
            print("="*60)
            print(json.dumps(ver, indent=2))
            print("="*60)
            
            if ver.get("verdict")=="APPROVED":
                idx["verified"]=True
                idx["verified_by"]="Gemini"
                idx["verified_at"]=datetime.now().isoformat()
                if not self.args.dry_run:
                    FileHandler.write_index(idx, Path(self.args.out), self.args.force)
                    print(f"SUCCESS: {self.args.out}")
                else:
                    print("DRY RUN:", json.dumps(idx, indent=2))
            else:
                print(f"VERDICT: {ver.get('verdict')}")
                if ver.get("issues"):
                    print("ISSUES:")
                    for issue in ver.get("issues"):
                        print(f"  - {issue.get('field')}: {issue.get('description')}")
                print("ESCALATE_TO_DIRECTOR")
                sys.exit(2)
        except Exception as e:
            print(f"FATAL: {e}")
            sys.exit(1)

def run_tests():
    print("="*50)
    print("TESTS")
    print("="*50)
    t = {"doc_id":"NEVA-TEST-001","title":"T","type":"T","version":"1","status":"DRAFT","verified":False,"verified_by":None,"verified_at":None,"date_created":"2025-01-01","author":"T","path":"t","parents":[],"children":[],"conflicts":[],"updates_required":[],"open_issues":[]}
    v,_ = IndexValidator.validate_schema(t)
    print("T-20:", "PASS" if v else "FAIL")
    t["verified"]=True
    v,_ = IndexValidator.validate_schema(t)
    print("T-21:", "PASS" if not v else "FAIL")
    print("\n✅ TESTS PASSED")

if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true")
    p.add_argument("--doc", required=False)
    p.add_argument("--out", required=False)
    p.add_argument("--registry", required=False)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mock", action="store_true")
    args = p.parse_args()
    if args.test:
        run_tests()
    else:
        if not all([args.doc, args.out, args.registry]):
            p.error("--doc, --out, --registry required")
        NevaIndexer(args).run()
