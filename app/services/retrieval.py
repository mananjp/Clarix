import re
import math
from typing import List, Dict, Any, Tuple

class RetrievalService:
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Convert text into a list of cleaned, lowercase alphanumeric tokens.
        """
        text = text.lower()
        # Find all words/numbers
        tokens = re.findall(r'[a-z0-9]+', text)
        # Simple stop words list
        stop_words = {
            "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent", "as",
            "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant", "cannot",
            "could", "couldnt", "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during", "each", "few",
            "for", "from", "further", "had", "hadnt", "has", "hasnt", "have", "havent", "having", "he", "hed", "hell",
            "hes", "her", "here", "heres", "hers", "herself", "him", "himself", "his", "how", "hows", "i", "id", "ill",
            "im", "ive", "if", "in", "into", "is", "isnt", "it", "its", "itself", "lets", "me", "more", "most", "mustnt",
            "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
            "ourselves", "out", "over", "own", "same", "shant", "she", "shed", "shell", "shes", "should", "shouldnt", "so",
            "some", "such", "than", "that", "thats", "the", "their", "theirs", "them", "themselves", "then", "there",
            "theres", "these", "they", "theyd", "theyll", "theyre", "theyve", "this", "those", "through", "to", "too",
            "under", "until", "up", "very", "was", "wasnt", "we", "wed", "well", "were", "weve", "werent", "what", "whats",
            "when", "whens", "where", "wheres", "which", "while", "who", "whos", "whom", "why", "whys", "with", "wont",
            "would", "wouldnt", "you", "youd", "youll", "youre", "youve", "your", "yours", "yourself", "yourselves"
        }
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    @classmethod
    def calculate_tfidf_scores(cls, query: str, documents: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        """
        Simple in-memory TF-IDF retriever. 
        documents: list of dicts with {"chunk_text": str, "id": str, ...}
        Returns list of (document, score) sorted by score descending.
        """
        query_tokens = cls.tokenize(query)
        if not query_tokens or not documents:
            return [(doc, 0.0) for doc in documents]

        # Count DF (Document Frequency) for terms in query
        df = {}
        for token in query_tokens:
            df[token] = 0
            for doc in documents:
                if token in cls.tokenize(doc.get("chunk_text", "")):
                    df[token] += 1

        N = len(documents)
        # Calculate IDF
        idf = {}
        for token, count in df.items():
            # Add-one smoothing to avoid division by zero
            idf[token] = math.log((N + 1) / (count + 1)) + 1.0

        scores = []
        for doc in documents:
            doc_text = doc.get("chunk_text", "")
            doc_tokens = cls.tokenize(doc_text)
            
            # Simple TF vector
            tf = {}
            for token in query_tokens:
                tf[token] = doc_tokens.count(token)

            # Cosine similarity-like score
            score = 0.0
            for token in query_tokens:
                if token in tf:
                    score += tf[token] * idf[token]
            
            # Normalize by document length to avoid favoring extremely long documents
            # (Basic length normalization)
            len_doc = len(doc_tokens)
            if len_doc > 0:
                score = score / math.sqrt(len_doc)
            
            scores.append((doc, score))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    @classmethod
    def search(cls, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Interface for retrieving top K relevant document chunks for a query.
        Returns a list of chunk dicts updated with a 'score' key.
        """
        scored_docs = cls.calculate_tfidf_scores(query, chunks)
        results = []
        
        # Take top K and ensure score > 0
        for doc, score in scored_docs[:top_k]:
            if score > 0:
                doc_copy = dict(doc)
                doc_copy["score"] = round(score, 4)
                results.append(doc_copy)
                
        # If no TF-IDF hits, fallback to simple keyword check or return top items
        if not results and chunks:
            # Fallback to return the first few chunks (sequential default)
            for doc in chunks[:2]:
                doc_copy = dict(doc)
                doc_copy["score"] = 0.05  # low baseline score
                results.append(doc_copy)
                
        return results
