# query_similar_companies.py

import torch
import pandas as pd
from pathlib import Path
import sys
import torch.nn.functional as F

# ---- 项目内 import ----
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config

class CompanySimilaritySearcher:
    def __init__(self, beta=0.5):
        """
        初始化相似度查询器。
        beta: PathSim 分数的融合权重。
        """
        self.beta = beta
        self.embeddings = None
        self.id_maps = None
        self.pathsim_map = {}
        self.company_neo4j_to_idx = {}
        self.company_idx_to_neo4j = {}
        
        self._load_data()
        self._preprocess_pathsim()

    def _load_data(self):
        """加载所有需要的数据：嵌入、ID映射、PathSim分数。"""
        print("Loading embeddings...")
        all_embeddings = torch.load(config.OUTPUT_EMBEDDINGS_PATH, weights_only=False)
        
        print("Loading ID maps...")
        self.id_maps = torch.load(config.ID_MAPS_PATH, weights_only=False)
        
        # 创建公司ID和索引之间的双向映射
        company_map_series = self.id_maps['Company']
        num_companies = len(company_map_series)
        self.company_neo4j_to_idx = {neo4j_id: idx for idx, neo4j_id in enumerate(company_map_series)}
        self.company_idx_to_neo4j = {idx: neo4j_id for neo4j_id, idx in self.company_neo4j_to_idx.items()}

        if 'Company' in all_embeddings:
            print("Detected per-type embedding tables.")
            self.embeddings = all_embeddings['Company']
        elif 'NODE' in all_embeddings:
            print("Detected a single 'NODE' embedding table.")
            # Slice the global embeddings to get only the ones for companies.
            # This assumes companies are the first block in the concatenated tensor.
            self.embeddings = all_embeddings['NODE'][:num_companies]
        else:
            raise KeyError("Could not find 'Company' or 'NODE' key in the embeddings file.")

        print("Loading PathSim scores...")
        pathsim_df = pd.read_csv(config.GRAPH_DIR / "company_pathsim_scores.csv")
        self.pathsim_df = pathsim_df

    def _preprocess_pathsim(self):
        """将PathSim DataFrame转换为一个高效查询的字典。"""
        print("Preprocessing PathSim scores for fast lookup...")
        for _, row in self.pathsim_df.iterrows():
            i, j, score = int(row['company_idx_1']), int(row['company_idx_2']), row['pathsim']
            # 创建双向映射
            self.pathsim_map[(i, j)] = score
            self.pathsim_map[(j, i)] = score

    def find_similar(self, target_company_id: str, top_k: int = 10):
        """
        查找与目标公司最相似的公司。
        target_company_id: 公司的Neo4j ID (例如 'company_123')
        """
        if target_company_id not in self.company_neo4j_to_idx:
            print(f"Error: Company ID '{target_company_id}' not found.")
            return

        target_idx = self.company_neo4j_to_idx[target_company_id]
        target_embedding = self.embeddings[target_idx].unsqueeze(0)

        # 1. 计算路1：嵌入余弦相似度
        cos_sim = F.cosine_similarity(target_embedding, self.embeddings)
        
        # 2. 应用 max(0, cos_sim)
        cos_sim_floored = torch.clamp(cos_sim, min=0)

        # 3. 融合分数
        num_companies = self.embeddings.size(0)
        final_scores = torch.zeros(num_companies)

        for j in range(num_companies):
            if j == target_idx:
                continue
            
            # 获取路2：PathSim分数 (如果不存在则为0)
            pathsim_score = self.pathsim_map.get((target_idx, j), 0.0)
            
            # 融合
            final_scores[j] = cos_sim_floored[j] + self.beta * pathsim_score
            
        # 4. 排序并返回结果
        top_k_indices = torch.topk(final_scores, k=top_k).indices
        
        results = []
        for idx in top_k_indices:
            j = idx.item()
            neo4j_id = self.company_idx_to_neo4j[j]
            results.append({
                "company_id": neo4j_id,
                "final_score": final_scores[j].item(),
                "cosine_sim": cos_sim[j].item(), # 显示原始cosine分
                "pathsim_score": self.pathsim_map.get((target_idx, j), 0.0)
            })
            
        return pd.DataFrame(results)


if __name__ == "__main__":
    # 示例用法
    # β 权重可以根据你的业务判断进行调整
    # 如果JV关系非常重要，可以设高一点，比如 0.8 或 1.0
    searcher = CompanySimilaritySearcher(beta=0.5)

    # 替换为你自己数据库中的公司ID
    target_id = 'comp_2' # 请替换为真实的ID, 例如力拓或必和必拓的ID

    print(f"\nFinding companies similar to '{target_id}' with beta={searcher.beta}...")
    similar_companies_df = searcher.find_similar(target_id, top_k=10)
    
    if similar_companies_df is not None:
        print(similar_companies_df.to_string())