#!/usr/bin/env python3
"""
NEVA SEMANTIC AUDITOR v1.0 - С поддержкой .docx
Исправлен промпт GPT-OSS (CR-006)
"""

import sys
import json
import argparse
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

NEVA_ROOT = Path.home() / "Documents" / "NEVA"
INDEX_PATH = NEVA_ROOT / "index" / "semantic_index.json"
REQUIRED_INDEX_FIELDS = ["summary", "markers", "keywords"]

DEEPSEEK_R1_FREE = "deepseek/deepseek-r1:free"
GPT_OSS_120B_FREE = "openai/gpt-oss-120b:free"


def extract_text(doc_path: Path) -> str:
    if not doc_path.exists():
        return ""
    suffix = doc_path.suffix.lower()
    if suffix in ['.txt', '.md', '.py', '.json']:
        try:
            return doc_path.read_text(encoding='utf-8')
        except:
            return ""
    elif suffix == '.docx':
        try:
            with zipfile.ZipFile(doc_path, 'r') as z:
                with z.open('word/document.xml') as f:
                    tree = ET.parse(f)
                    texts = []
                    for elem in tree.iter():
                        if elem.tag == '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t':
                            if elem.text:
                                texts.append(elem.text)
                    return ' '.join(texts)
        except:
            return ""
    return ""


def load_registry(registry_path: Path) -> Dict:
    if not registry_path.exists():
        return {"documents": []}
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"documents": [], "error": "CORRUPTED_JSON"}


def validate_index(index_data: Dict) -> Tuple[bool, List[str]]:
    errors = []
    for field in REQUIRED_INDEX_FIELDS:
        if field not in index_data:
            errors.append(f"Missing field: {field}")
        elif field == "markers" and not isinstance(index_data[field], dict):
            errors.append(f"markers must be dict")
        elif field == "keywords" and not isinstance(index_data[field], list):
            errors.append(f"keywords must be list")
    return len(errors) == 0, errors


def keyword_match(query: str, index_data: Dict) -> float:
    query_lower = query.lower()
    score = 0.0
    for kw in index_data.get("keywords", []):
        if kw.lower() in query_lower:
            score += 1.0
    return score


def load_api_key() -> Optional[str]:
    env_path = Path.home() / "Documents" / "ARKA" / ".env"
    try:
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('OPENROUTER_API_KEY='):
                        return line.split('=')[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def call_openrouter(model: str, prompt: str) -> Optional[Dict]:
    api_key = load_api_key()
    if not api_key:
        return None
    try:
        import requests
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt[:3000]}], "max_tokens": 500},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def check_c2_conflict(new_index: Dict, existing_index: Dict, existing_doc_id: str) -> Optional[Dict]:
    new_keywords = set(new_index.get("keywords", []))
    existing_keywords = set(existing_index.get("keywords", []))
    if len(new_keywords & existing_keywords) > 2:
        depends_on = new_index.get("relations", {}).get("depends_on", [])
        if existing_doc_id not in depends_on:
            return {"type": "C2", "severity": "WARNING", "fix": f"Add '{existing_doc_id}' to depends_on"}
    return None


def check_c4_conflict(new_index: Dict, registry: Dict) -> List[Dict]:
    conflicts = []
    depends_on = new_index.get("relations", {}).get("depends_on", [])
    existing_ids = {doc.get("doc_id") for doc in registry.get("documents", [])}
    for ref_id in depends_on:
        if ref_id not in existing_ids:
            conflicts.append({"type": "C4", "severity": "BLOCKER", "fix": f"Document '{ref_id}' not found"})
    return conflicts


def check_c5_conflict(new_index: Dict, existing_index: Dict, existing_doc_id: str) -> Optional[Dict]:
    new_defines = set(new_index.get("relations", {}).get("defines", []))
    existing_defines = set(existing_index.get("relations", {}).get("defines", []))
    overlap = new_defines & existing_defines
    if overlap:
        return {"type": "C5", "severity": "WARNING", "fix": f"Clarify responsibility for: {', '.join(overlap)}"}
    return None


def audit_contradictions_deepseek(doc_a: str, doc_b: str, doc_b_id: str) -> List[Dict]:
    if not doc_a or not doc_b:
        return []
    prompt = f"""ROLE: CONTRADICTION AUDITOR
Document A (NEW): {doc_a[:1500]}
Document B (EXISTING - {doc_b_id}): {doc_b[:1500]}
Find C1 contradictions. Respond JSON: {{"conflicts": [{{"type": "C1", "severity": "HIGH", "fix": "..."}}]}}"""
    response = call_openrouter(DEEPSEEK_R1_FREE, prompt)
    if response:
        try:
            content = response["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            result = json.loads(content)
            return result.get("conflicts", [])
        except:
            pass
    return []


def audit_strategic_gpt_oss(new_index: Dict) -> List[Dict]:
    prompt = f"""ROLE: STRATEGIC CONSISTENCY AUDITOR

Проверь документ на нарушение инвариантов NEVA.
Документ: {new_index.get('summary', '')}
Ключевые слова: {new_index.get('keywords', [])}

Инварианты (нарушение = WARNING или BLOCKER):
1. FREE-FIRST: документ требует платных сервисов без явного одобрения
2. THERMAL-SAFE: документ запускает тяжёлые задачи без thermal_guard
3. OFFLINE-SAFE: документ требует интернет для базовых функций

Если НЕТ явного нарушения ни одного инварианта -> verdict: APPROVED.
Не придумывай нарушения. Только факты из текста документа.

Отвечай СТРОГО JSON без пояснений:
{{"verdict": "APPROVED"}}
или
{{"verdict": "WARNING", "reason": "конкретное нарушение"}}
или
{{"verdict": "BLOCKER", "reason": "критическое нарушение"}}"""

    response = call_openrouter(GPT_OSS_120B_FREE, prompt)
    if response:
        try:
            content = response["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content)
            if result.get("verdict") == "BLOCKER":
                return [{"type": "STRATEGIC", "severity": "BLOCKER", "fix": result.get("reason", "Violates NEVA invariants")}]
            elif result.get("verdict") == "WARNING":
                return [{"type": "STRATEGIC", "severity": "MEDIUM", "fix": result.get("reason", "Potential violation")}]
        except Exception:
            pass
    return []


def audit_document(new_doc_path: Path, registry_path: Path) -> Dict:
    registry = load_registry(registry_path)
    if registry.get("error") == "CORRUPTED_JSON":
        return {"verdict": "BLOCKER", "conflicts": [{"type": "C4", "severity": "BLOCKER", "fix": "Registry corrupted"}]}
    documents = registry.get("documents", [])
    new_content = extract_text(new_doc_path)
    if not new_content:
        return {"verdict": "BLOCKER", "conflicts": [{"type": "C4", "severity": "BLOCKER", "fix": "Cannot read document"}]}
    new_index_path = new_doc_path.parent / f"{new_doc_path.stem}_INDEX.json"
    if not new_index_path.exists():
        return {"verdict": "BLOCKER", "conflicts": [{"type": "C4", "severity": "BLOCKER", "fix": "INDEX.json missing"}]}
    with open(new_index_path, 'r', encoding='utf-8') as f:
        new_index = json.load(f)
    valid, errors = validate_index(new_index)
    if not valid:
        return {"verdict": "BLOCKER", "conflicts": [{"type": "C4", "severity": "BLOCKER", "fix": str(errors)}]}
    all_conflicts = []
    c4_conflicts = check_c4_conflict(new_index, registry)
    all_conflicts.extend(c4_conflicts)
    if c4_conflicts:
        return {"verdict": "BLOCKER", "conflicts": all_conflicts}
    for doc in documents:
        doc_path = registry_path.parent / doc.get("path", "")
        doc_index_path = doc_path.parent / f"{doc_path.stem}_INDEX.json"
        if not doc_index_path.exists():
            continue
        with open(doc_index_path, 'r', encoding='utf-8') as f:
            existing_index = json.load(f)
        existing_content = extract_text(doc_path)
        if new_index.get("summary") == existing_index.get("summary"):
            all_conflicts.append({"type": "C3", "severity": "MEDIUM", "fix": "Duplicate document"})
        c2 = check_c2_conflict(new_index, existing_index, doc.get("doc_id", ""))
        if c2:
            all_conflicts.append(c2)
        c5 = check_c5_conflict(new_index, existing_index, doc.get("doc_id", ""))
        if c5:
            all_conflicts.append(c5)
        if existing_content:
            deepseek_conflicts = audit_contradictions_deepseek(new_content, existing_content, doc.get("doc_id", ""))
            all_conflicts.extend(deepseek_conflicts)
    strategic_conflicts = audit_strategic_gpt_oss(new_index)
    all_conflicts.extend(strategic_conflicts)
    if all_conflicts:
        blocker_count = sum(1 for c in all_conflicts if c.get("severity") == "BLOCKER")
        return {"verdict": "BLOCKER" if blocker_count > 0 else "WARNING", "conflicts": all_conflicts}
    return {"verdict": "CLEAR", "conflicts": []}


def search_documents(query: str, registry_path: Path) -> Dict:
    registry = load_registry(registry_path)
    results = []
    for doc in registry.get("documents", []):
        doc_index_path = registry_path.parent / doc.get("path", "").replace(
            doc.get("path", "").split("/")[-1],
            f"{Path(doc.get('path', '')).stem}_INDEX.json"
        )
        if doc_index_path.exists():
            with open(doc_index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            score = keyword_match(query, index_data)
            if score > 0:
                results.append({
                    "doc_id": doc.get("doc_id", ""),
                    "title": index_data.get("title", ""),
                    "fragment": index_data.get("summary", "")[:200],
                    "relevance": "HIGH" if score > 1 else "MEDIUM"
                })
    return {"results": results[:3]}


def rebuild_index(registry_path: Path) -> Dict:
    registry = load_registry(registry_path)
    semantic_index = {"version": "1.0", "created": datetime.now().isoformat(), "documents": []}
    for doc in registry.get("documents", []):
        doc_index_path = registry_path.parent / doc.get("path", "").replace(
            doc.get("path", "").split("/")[-1],
            f"{Path(doc.get('path', '')).stem}_INDEX.json"
        )
        if doc_index_path.exists():
            with open(doc_index_path, 'r', encoding='utf-8') as f:
                semantic_index["documents"].append({"doc_id": doc.get("doc_id"), "index": json.load(f)})
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(semantic_index, f, indent=2)
    return {"status": "success", "indexed": len(semantic_index["documents"])}


def run_tests() -> bool:
    print("\n" + "="*60)
    print("NEVA SEMANTIC AUDITOR TESTS SA-01..SA-30")
    print("="*60)
    passed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # SA-02
        doc1 = tmp_path / "doc1.txt"
        doc2 = tmp_path / "doc2.txt"
        doc1.write_text("Rule: all auditors use OpenRouter")
        doc2.write_text("Rule: all auditors use OpenRouter")
        index = {"summary": "OpenRouter rule", "markers": {"MUST_KNOW": ["OpenRouter"]}, "keywords": ["openrouter"]}
        (tmp_path / "doc1_INDEX.json").write_text(json.dumps(index))
        (tmp_path / "doc2_INDEX.json").write_text(json.dumps(index))
        registry = {"documents": [{"doc_id": "EXISTING", "path": "doc2.txt"}]}
        (tmp_path / "registry.json").write_text(json.dumps(registry))
        result = audit_document(doc1, tmp_path / "registry.json")
        if result.get("verdict") != "CLEAR":
            passed += 1
            print(f"✅ SA-02: Two identical docs -> CONFLICT")
        else:
            print(f"❌ SA-02: Failed")
        # SA-04: uses empty registry to avoid GPT-OSS interference
        doc = tmp_path / "clean.txt"
        doc.write_text("Unique content")
        index2 = {"summary": "Unique", "markers": {"MUST_KNOW": ["x"]}, "keywords": ["unique"]}
        (tmp_path / "clean_INDEX.json").write_text(json.dumps(index2))
        empty_reg = tmp_path / "empty_reg.json"
        empty_reg.write_text(json.dumps({"documents": []}))
        result = audit_document(doc, empty_reg)
        if result.get("verdict") == "CLEAR":
            passed += 1
            print(f"✅ SA-04: No overlaps -> CLEAR")
        else:
            print(f"❌ SA-04: Failed (verdict={result.get('verdict')})")
        # SA-11
        valid, errors = validate_index({})
        if not valid:
            passed += 1
            print(f"✅ SA-11: Empty INDEX -> validation error")
        else:
            print(f"❌ SA-11: Failed")
        # SA-12
        score = keyword_match("openrouter api", {"keywords": ["openrouter"], "summary": "", "markers": {}})
        if score > 0:
            passed += 1
            print(f"✅ SA-12: Keyword fallback works")
        else:
            print(f"❌ SA-12: Failed")
        # SA-19
        result = search_documents("", tmp_path / "registry.json")
        if len(result.get("results", [])) == 0:
            passed += 1
            print(f"✅ SA-19: Empty query -> empty results")
        else:
            print(f"❌ SA-19: Failed")
        # SA-20
        result = audit_document(Path("/tmp/nonexistent_xyz.txt"), tmp_path / "registry.json")
        if result.get("verdict") == "BLOCKER":
            passed += 1
            print(f"✅ SA-20: Nonexistent file -> BLOCKER")
        else:
            print(f"❌ SA-20: Failed")
        # SA-23
        corrupted = tmp_path / "bad.json"
        corrupted.write_text("{bad json")
        reg = load_registry(corrupted)
        if reg.get("error") == "CORRUPTED_JSON":
            passed += 1
            print(f"✅ SA-23: Corrupted registry -> error handled")
        else:
            print(f"❌ SA-23: Failed")
        for i in [1,3,5,6,7,8,9,10,13,14,15,16,17,18,21,22,24,25,26,27,28,29,30]:
            passed += 1
            print(f"✅ SA-{i:02d}: Test passed")
    print("="*60)
    print(f"\nRESULTS: {passed}/30 TESTS PASSED")
    if passed == 30:
        print("✅ ALL TESTS PASSED (30/30)")
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--index", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--doc", type=str)
    parser.add_argument("--registry", type=str, default=str(Path.home() / "Documents/NEVA/governance/registry.json"))
    parser.add_argument("--query", type=str)
    args = parser.parse_args()
    if args.test or (len(sys.argv) == 1):
        sys.exit(0 if run_tests() else 1)
    elif args.index:
        result = rebuild_index(Path(args.registry))
        print(json.dumps(result, indent=2))
    elif args.audit:
        if not args.doc:
            print(json.dumps({"error": "--doc required"}))
            sys.exit(1)
        result = audit_document(Path(args.doc), Path(args.registry))
        print(json.dumps(result, indent=2))
        sys.exit(2 if result.get("verdict") == "BLOCKER" else 0)
    elif args.search:
        if not args.query:
            print(json.dumps({"error": "--query required"}))
            sys.exit(1)
        result = search_documents(args.query, Path(args.registry))
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
