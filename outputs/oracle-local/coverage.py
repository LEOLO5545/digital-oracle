"""Final unique-response counts, including supplemental queries and retries."""
def signal_counts(plan,rows):
 unique={r['id']:r for r in rows}
 return {'planned':len({s['id'] for s in plan.get('signals',[])}),'received':len(unique),'successful':sum(r.get('status')=='ok' for r in unique.values()),'failed':sum(r.get('status')=='error' for r in unique.values())}

def coverage_text(counts):
 return f"{counts['successful']} 個已取得訊號 · {counts['failed']} 個取數失敗 · {counts['planned']} 個規劃訊號；回應數不等於獨立分析維度。"
