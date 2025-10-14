# calculate_pathsim.py

import torch
import pandas as pd
from pathlib import Path
import sys
from scipy.sparse import csr_matrix, save_npz, load_npz

# ---- 项目内 import ----
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config

def calculate_company_project_pathsim(data, company_node_type='Company', project_node_type='Project'):
    """
    计算并保存 C-P-C PathSim 分数。
    data: PyG 的 HeteroData 对象。
    """
    print("Calculating PathSim for Company-Project-Company...")

    # 1. 获取 (Company, OWNS, Project) 的边索引
    #    注意：这里的关系名 'OWNS' 需要和你的 HeteroData edge_type 中的完全一致
    try:
        # 修正：关系名应为大写的 'OWNS'
        edge_index = data[company_node_type, 'OWNS', project_node_type].edge_index
    except KeyError:
        # 如果关系名有其他形式，请在这里修改
        print(f"Error: Edge type ('{company_node_type}', 'OWNS', '{project_node_type}') not found.")
        print("Please check your RELATION_TYPES and adjust the key in the script.")
        return None

    company_indices = edge_index[0]
    project_indices = edge_index[1]

    num_companies = data[company_node_type].num_nodes
    num_projects = data[project_node_type].num_nodes

    # 2. 构建公司-项目邻接矩阵 A_CP (稀疏矩阵)
    #    这是一个 |C| x |P| 的矩阵，如果公司 c 拥有项目 p，则 A_CP[c, p] = 1
    print(f"Building adjacency matrix for {num_companies} companies and {num_projects} projects...")
    A_cp = csr_matrix((torch.ones(edge_index.size(1)), (company_indices, project_indices)),
                      shape=(num_companies, num_projects))

    # 3. 计算 M = A_CP * A_CP^T
    #    M 是一个 |C| x |C| 的矩阵，M[i, j] 是公司 i 和 j 共同拥有的项目数
    #    M 的对角线 M[i, i] 是公司 i 拥有的项目总数
    print("Calculating M = A_CP * A_CP.T (this may take a moment)...")
    M = A_cp.dot(A_cp.T)

    # 4. 计算 PathSim 分数
    #    PathSim(i, j) = 2 * M[i, j] / (M[i, i] + M[j, j])
    #    为了避免除以零，我们只在 M[i,i] + M[j,j] > 0 时计算
    print("Calculating PathSim scores...")
    M_diag = M.diagonal()
    
    # 找到 M 中非零元素的坐标 (i, j)
    rows, cols = M.nonzero()
    
    pathsim_scores = []
    for i, j in zip(rows, cols):
        if i >= j:  # 只计算上三角部分，因为矩阵是对称的
            continue
        
        numerator = 2 * M[i, j]
        denominator = M_diag[i] + M_diag[j]
        
        if denominator > 0:
            score = numerator / denominator
            pathsim_scores.append({'company_idx_1': i, 'company_idx_2': j, 'pathsim': score})

    df_pathsim = pd.DataFrame(pathsim_scores)
    
    # 5. 保存结果
    output_path = config.GRAPH_DIR / "company_pathsim_scores.csv"
    df_pathsim.to_csv(output_path, index=False)
    print(f"PathSim scores saved to '{output_path}'")
    
    # (可选) 保存稀疏矩阵 M，便于未来快速加载
    # save_npz(config.GRAPH_DIR / "company_cocitation_matrix.npz", M)

def main():
    """
    主执行函数
    """
    print("Loading graph data...")
    # 加载异构图数据对象
    data = torch.load(config.HETERO_DATA_PATH, weights_only=False)

    # 加载公司ID映射
    id_maps = torch.load(config.ID_MAPS_PATH, weights_only=False)

    # 确保 data 中有 num_nodes 属性
    if not hasattr(data['Company'], 'num_nodes') or not hasattr(data['Project'], 'num_nodes'):
         print("Inferring num_nodes from edges as it's missing in the data object...")
         from train_metapath2vec import infer_num_nodes_dict_from_edges
         num_nodes_dict = infer_num_nodes_dict_from_edges(data)
         data['Company'].num_nodes = num_nodes_dict.get('Company', 0)
         data['Project'].num_nodes = num_nodes_dict.get('Project', 0)

    calculate_company_project_pathsim(data)

if __name__ == "__main__":
    main()