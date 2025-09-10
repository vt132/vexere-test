import csv
import os
from typing import List, Dict, Optional
from pathlib import Path
import difflib
from ..config import FAQ_DATA_PATH
def load_faq_data() -> List[Dict[str, str]]:
	faqs = []
	if not FAQ_DATA_PATH.exists():
		return faqs
	with open(FAQ_DATA_PATH, encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			faqs.append({k.strip(): v.strip() for k, v in row.items()})
	return faqs

_FAQ_CACHE = None
def get_faqs() -> List[Dict[str, str]]:
	global _FAQ_CACHE
	if _FAQ_CACHE is None:
		_FAQ_CACHE = load_faq_data()
	return _FAQ_CACHE

def retrieve_faq(question: str, top_k: int = 1) -> List[Dict[str, str]]:
	faqs = get_faqs()
	if not faqs:
		return []
	# Use difflib for simple fuzzy matching on 'question' field
	questions = [f["question"] for f in faqs if "question" in f]
	matches = difflib.get_close_matches(question, questions, n=top_k, cutoff=0.3)
	return [f for f in faqs if f["question"] in matches]
