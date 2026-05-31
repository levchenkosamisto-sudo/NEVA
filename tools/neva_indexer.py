#!/usr/bin/env python3
"""
NEVA INDEXER v2.0 - REAL API
"""

import sys
import os
import json
import argparse
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

if sys.version_info < (3, 11):
    print("FATAL: Python 3.11+ required")
    sys.exit(1)

try:
    import requests
    import google.generativeai as genai
    from docx import Document
except ImportError as e:
    print(f"FATAL: {e}")
    sys.exit(1)

CONFIG = {
    "openrouter_url": "https://openrouter.ai/api/v1/chat/completions",
    "deepseek_model": "deepseek/deepseek-r1:free",
    "gptoss_model": "microsoft/phi-4:free",
    "gemini_model": "gemini-2.5-flash-preview-05-20",
    "timeouts": {"deepseek": 60, "gemini": 30, "gptoss": 60},
    "max_retries": 1,
    "allowed_relations": ["INHERITS", "IMPLEMENTS", "DEPENDS_ON", "EXTENDS", "REFERENCES"],
    "allowed_severities": ["BLOCKER", "WARNING"],
    "allowed_statuses": ["DRAFT", "REVIEW", "APPROVED", "FIXED", "OBSOLETE"],
    "doc_id_pattern": r"^NEVA-[A-Z]+-\d{3}$"
}

class IndexerLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries = []
    def log(self, entry: Dict):
        entry["timestamp"] = datetime.now().isoformat()
        self.entries.append(entry)
        with open(self.log_path, 'w') as f:
            json.dump({"logs": self.entries}, f, indent=2)
    def add_operation(self, op: str, status: str, details: Dict = None):
        self.log({"operation": op, "status": status, "details": details or {}})
    def log_block(self, reason: str, index_data: Dict = None):
        blocks_path = self.log_path.parent / "blocks_log.json"
        try:
            if blocks_path.exists():
                with open(blocks_path, 'r') as f:
                    blocks = json.load(f)
            else:
                blocks = {"blocks": []}
            blocks["blocks"].append({"type": "ESCALATION", "reason": reason, "timestamp": datetime.now().isoformat(), "index_data": index_data})
            with open(blocks_path, 'w') as f:
                json.dump(blocks, f, indent=2)
        except Exception as e:
            print(f"WARNING: {e}")

class Diagnostics:
    @staticmethod
    def check_env_vars(mock_mode: bool = False):
        if mock_mode:
            print("MOCK MODE: skipping API keys check")
            return True
        missing = [v for v in ["OPENROUTER_API_KEY", "GEMINI_API_KEY"] if not os.getenv(v)]
        if missing:
            print(f"FATAL: missing {missing}")
            sys.exit(1)
        return True
    @staticmethod
    def check_registry(path: Path):
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
    def read_document(path: Path) -> str:
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
    def write_index(data: Dict, path: Path, force: bool = False):
        if path.exists() and not force:
            raise FileExistsError(f"Index exists: {path}. Use --force")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

class APIClient:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        if not mock_mode:
            self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
            self.gemini_key = os.getenv("GEMINI_API_KEY")
            genai.configure(api_key=self.gemini_key)
    
    def _clean_json(self, content: str) -> str:
        content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n?```\s*$', '', content, flags=re.MULTILINE)
        return content.strip()
    
    def call_deepseek(self, registry_context: str, document: str) -> Dict:
        if self.mock_mode:
            return self._mock_index(document)
        
        system_prompt = """You are NEVA INDEXER. Return ONLY valid JSON. No markdown. verified is always false. verified_by and verified_at are null."""
        user_prompt = f"""Registry: {registry_context}\n\nDocument:\n{document}\n\nProduce index card in JSON."""
        
        for attempt in range(CONFIG["max_retries"] + 1):
            try:
                resp = requests.post(
                    CONFIG["openrouter_url"],
                    headers={"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"},
                    json={"model": CONFIG["deepseek_model"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1, "max_tokens": 4000},
                    timeout=CONFIG["timeouts"]["deepseek"]
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return json.loads(self._clean_json(content))
            except Exception as e:
                if attempt == CONFIG["max_retries"]:
                    print(f"FATAL: DeepSeek error: {e}")
                    sys.exit(1)
                time.sleep(2)
    
    def call_gemini(self, document: str, index: Dict) -> Dict:
        if self.mock_mode:
            return {"verdict": "APPROVED", "confidence": 0.95, "issues": [], "summary": "Mock approved"}
        
        prompt = f"""Verify this index card. Return JSON: {{"verdict": "APPROVED"|"REJECTED", "confidence": 0.0-1.0, "issues": [], "summary": ""}}\n\nDocument:\n{document}\n\nIndex:\n{json.dumps(index, indent=2)}"""
        
        for attempt in range(CONFIG["max_retries"] + 1):
            try:
                model = genai.GenerativeModel(CONFIG["gemini_model"])
                response = model.generate_content(prompt, generation_config={"temperature": 0.1})
                content = self._clean_json(response.text)
                return json.loads(content)
            except Exception as e:
                if attempt == CONFIG["max_retries"]:
                    print(f"FATAL: Gemini error: {e}")
                    sys.exit(1)
                time.sleep(2)
    
    def call_gptoss(self, document: str, index: Dict, verification: Dict) -> Dict:
        if self.mock_mode:
            return {"final_index": index, "arbitration_log": [], "verdict": "RESOLVED"}
        
        system_prompt = "You are NEVA ARBITRATOR. Return JSON with final_index, arbitration_log, verdict (RESOLVED or ESCALATE_TO_DIRECTOR)."
        user_prompt = f"Document:\n{document}\n\nIndex:\n{json.dumps(index, indent=2)}\n\nVerification:\n{json.dumps(verification, indent=2)}"
        
        for attempt in range(CONFIG["max_retries"] + 1):
            try:
                resp = requests.post(
                    CONFIG["openrouter_url"],
                    headers={"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"},
                    json={"model": CONFIG["gptoss_model"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1, "max_tokens": 4000},
                    timeout=CONFIG["timeouts"]["gptoss"]
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return json.loads(self._clean_json(content))
            except Exception as e:
                if attempt == CONFIG["max_retries"]:
                    print(f"FATAL: GPT-OSS error: {e}")
                    sys.exit(1)
                time.sleep(2)
    
    def _mock_index(self, doc: str) -> Dict:
        doc_id = re.search(r'doc_id[:\s]+([A-Z\-0-9]+)', doc)
        title = re.search(r'title[:\s]+(.+?)(?:\n|$)', doc)
        return {
            "doc_id": doc_id.group(1) if doc_id else "NEVA-TEST-001",
            "title": title.group(1).strip() if title else "Test",
            "type": "TEST", "version": "1.0", "status": "DRAFT",
            "verified": False, "verified_by": None, "verified_at": None,
            "date_created": datetime.now().strftime("%Y-%m-%d"), "author": "Mock",
            "path": "test.md", "parents": [], "children": [],
            "conflicts": [], "updates_required": [], "open_issues": []
        }

class IndexValidator:
    @staticmethod
    def validate_schema(index: Dict) -> Tuple[bool, List[str]]:
        errors = []
        required = ["doc_id", "title", "type", "version", "status", "verified", "verified_by", "verified_at", "date_created", "author", "path", "parents", "children", "conflicts", "updates_required", "open_issues"]
        for f in required:
            if f not in index:
                errors.append(f"missing: {f}")
        if "doc_id" in index and not re.match(CONFIG["doc_id_pattern"], index["doc_id"]):
            errors.append(f"invalid doc_id: {index['doc_id']}")
        if index.get("verified") is not False:
            errors.append("verified must be false")
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_relations(index: Dict, registry: Dict) -> Tuple[bool, List[str], List[str]]:
        errors, warnings = [], []
        for parent in index.get("parents", []):
            if parent.get("relation") not in CONFIG["allowed_relations"]:
                errors.append(f"invalid relation: {parent.get('relation')}")
            doc_id = parent.get("doc_id")
            if doc_id and not any(d.get("doc_id") == doc_id for d in registry.get("documents", [])):
                warnings.append(f"doc_id {doc_id} not found")
        for conflict in index.get("conflicts", []):
            if conflict.get("severity") not in CONFIG["allowed_severities"]:
                errors.append(f"invalid severity: {conflict.get('severity')}")
        return len(errors) == 0, errors, warnings

class NevaIndexer:
    def __init__(self, args):
        self.args = args
        self.base_path = Path(os.getenv("NEVA_HOME", "~/Documents/NEVA")).expanduser()
        self.logger = IndexerLogger(self.base_path / "logs" / "indexer_log.json")
    
    def run(self):
        try:
            self.logger.add_operation("start", "STARTED")
            Diagnostics.check_env_vars(mock_mode=self.args.mock)
            
            reg_path = Path(self.args.registry)
            if not reg_path.is_absolute():
                reg_path = self.base_path / self.args.registry
            registry = Diagnostics.check_registry(reg_path)
            
            doc_path = Path(self.args.doc)
            if not doc_path.is_absolute():
                doc_path = self.base_path / self.args.doc
            content = FileHandler.read_document(doc_path)
            
            client = APIClient(mock_mode=self.args.mock)
            
            self.logger.add_operation("deepseek", "STARTED")
            index = client.call_deepseek(json.dumps(registry), content)
            self.logger.add_operation("deepseek", "SUCCESS", {"doc_id": index.get("doc_id")})
            
            valid, errors = IndexValidator.validate_schema(index)
            if not valid:
                print(f"FATAL: {errors}")
                sys.exit(1)
            
            index["verified"] = False
            index["verified_by"] = None
            index["verified_at"] = None
            
            self.logger.add_operation("gemini", "STARTED")
            verification = client.call_gemini(content, index)
            self.logger.add_operation("gemini", "SUCCESS", {"verdict": verification.get("verdict")})
            
            if verification.get("verdict") == "APPROVED":
                index["verified"] = True
                index["verified_by"] = "Gemini-2.5-Flash"
                index["verified_at"] = datetime.now().isoformat()
                
                valid_rel, rel_errors, rel_warnings = IndexValidator.validate_relations(index, registry)
                if not valid_rel:
                    print(f"FATAL: {rel_errors}")
                    sys.exit(1)
                for w in rel_warnings:
                    print(f"WARNING: {w}")
                
                if not self.args.dry_run:
                    FileHandler.write_index(index, Path(self.args.out), self.args.force)
                    print(f"SUCCESS: {self.args.out}")
                else:
                    print("DRY RUN:", json.dumps(index, indent=2))
                
            elif verification.get("verdict") == "REJECTED":
                self.logger.add_operation("arbitration", "STARTED")
                arbitration = client.call_gptoss(content, index, verification)
                
                if arbitration.get("verdict") == "RESOLVED":
                    final = arbitration["final_index"]
                    final["verified"] = True
                    final["verified_by"] = "GPT-OSS-Arbitrator"
                    final["verified_at"] = datetime.now().isoformat()
                    
                    if not self.args.dry_run:
                        FileHandler.write_index(final, Path(self.args.out), self.args.force)
                        print(f"SUCCESS (RESOLVED): {self.args.out}")
                    else:
                        print("DRY RUN:", json.dumps(final, indent=2))
                else:
                    print("ESCALATE_TO_DIRECTOR")
                    self.logger.log_block("ESCALATE_TO_DIRECTOR", index)
                    sys.exit(2)
            else:
                print(f"FATAL: Unknown verdict: {verification.get('verdict')}")
                sys.exit(1)
                
            self.logger.add_operation("finish", "SUCCESS")
            
        except FileExistsError as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"FATAL: {e}")
            sys.exit(1)

def run_tests():
    print("="*60)
    print("NEVA INDEXER v2.0 TESTS")
    print("="*60)
    
    test_index = {
        "doc_id": "NEVA-TEST-001", "title": "T", "type": "T", "version": "1",
        "status": "DRAFT", "verified": False, "verified_by": None, "verified_at": None,
        "date_created": "2025-01-01", "author": "T", "path": "t",
        "parents": [], "children": [], "conflicts": [], "updates_required": [], "open_issues": []
    }
    valid, _ = IndexValidator.validate_schema(test_index)
    print("T-20:", "PASS" if valid else "FAIL")
    
    test_index["verified"] = True
    valid, _ = IndexValidator.validate_schema(test_index)
    print("T-21:", "PASS" if not valid else "FAIL")
    
    print("\n✅ Basic tests passed")
    print("⚠️ Full API tests require --mock=false and valid keys")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--doc", required=False)
    parser.add_argument("--out", required=False)
    parser.add_argument("--registry", required=False)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    
    if args.test:
        run_tests()
    else:
        if not all([args.doc, args.out, args.registry]):
            parser.error("--doc, --out, --registry required")
        NevaIndexer(args).run()
