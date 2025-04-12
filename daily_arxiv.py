import os
import re
import json
import arxiv
import yaml
import logging
import argparse
import datetime
import requests
from typing import Dict, List

# 配置日志
logging.basicConfig(
    format='[%(asctime)s %(levelname)s] %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S',
    level=logging.INFO
)

# 全局常量
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARXIV_URL = "http://arxiv.org/"
GITHUB_API_URL = "https://api.github.com/search/repositories"

def load_config(config_file: str) -> Dict:
    # workspace = os.environ.get('GITHUB_WORKSPACE', os.getcwd())
    """加载并处理配置文件"""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
        
        # 为每个分类生成完整路径
        for cat in config['categories'].values():
            # cat['output_dir'] = os.path.join(workspace, cat['output_dir'])
            cat['json_path'] = os.path.join(cat['output_dir'], 'papers.json')
            cat['md_path'] = os.path.join(cat['output_dir'], 'README.md')
            
        logging.info(f"Loaded configuration: {json.dumps(config, indent=2)}")
        return config

def get_authors(authors, first_author: bool = False) -> str:
    """格式化作者列表"""
    return authors[0].name if first_author else ", ".join(a.name for a in authors)

def sort_papers(papers: Dict) -> Dict:
    """按日期排序论文"""
    return dict(sorted(papers.items(), key=lambda x: x[0], reverse=True))

def get_code_link(paper_id: str) -> str:
    """获取论文代码链接"""
    try:
        code_url = f"https://arxiv.paperswithcode.com/api/v0/papers/{paper_id}"
        response = requests.get(code_url).json()
        return response.get('official', {}).get('url')
    except Exception as e:
        logging.error(f"Failed to get code link for {paper_id}: {str(e)}")
        return None

def fetch_papers(query: str, max_results: int) -> Dict:
    """获取指定查询的论文"""
    client = Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    papers = {}
    for result in client.results(search):
        paper_id = result.get_short_id()
        update_time = result.updated.date()
        
        # 处理版本号
        clean_id = paper_id.split('v')[0]
        pdf_url = f"{ARXIV_URL}abs/{clean_id}"

        abstract = result.summary.replace("\n", " ")
        
        # 获取代码链接
        code_link = get_code_link(clean_id) or "null"
        
        papers[paper_id] = {
            "title": result.title,
            "authors": get_authors(result.authors),
            "abstract": abstract,
            "pdf": pdf_url,
            "code": code_link,
            "updated": str(update_time)
        }
    
    print("paper.len: ", len(papers))
    
    # return papers

def update_category_data(category_config: Dict, global_config: Dict):
    """更新单个分类的数据"""
    # 创建输出目录
    os.makedirs(category_config['output_dir'], exist_ok=True)
    
    # 获取论文数据
    papers = fetch_papers(
        query=category_config['query'],
        max_results=global_config['max_results']
    )
    
    # 加载现有数据
    existing_data = {}
    if os.path.exists(category_config['json_path']):
        with open(category_config['json_path'], 'r') as f:
            existing_data = json.load(f)
    
    # 合并新数据（去重）
    merged_data = {**papers, **existing_data}
    
    # 保存更新后的数据
    with open(category_config['json_path'], 'w') as f:
        json.dump(merged_data, f, indent=2)
    
    # 生成Markdown
    generate_markdown(
        data=merged_data,
        output_path=category_config['md_path'],
        category_name=os.path.basename(category_config['output_dir'])
    )

def generate_markdown(data: Dict, output_path: str, category_name: str):
    """生成分类专属的Markdown文件"""
    # 排序论文
    sorted_papers = sorted(data.values(), 
                         key=lambda x: x['updated'], 
                         reverse=True)
    
    # 构建Markdown内容
    content = [
        f"# {category_name.replace('-', ' ').title()} Papers",
        f"*Last Updated: {datetime.date.today().strftime('%Y-%m-%d')}*\n",
        "| Date | Title | Authors | PDF | Code |",
        "|------|-------|---------|-----|------|"
    ]
    
    for paper in sorted_papers:
        code_link = f"[Code]({paper['code']})" if paper['code'] != "null" else "null"
        row = f"| {paper['updated']} | {paper['title']} | {paper['authors']} | " \
              f"[PDF]({paper['pdf']}) | {code_link} |"
        content.append(row)
    
    # 写入文件
    with open(output_path, 'w') as f:
        f.write("\n".join(content))
    logging.info(f"Generated markdown for {category_name} at {output_path}")

def main(config: Dict):
    """主处理流程"""
    for cat_name, cat_config in config['categories'].items():
        logging.info(f"🚀 Processing category: {cat_name}")
        try:
            update_category_data(cat_config, config)
            logging.info(f"Successfully updated {cat_name}")
        except Exception as e:
            logging.error(f"Failed to process {cat_name}: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ArXiv论文追踪系统')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='配置文件路径')
    args = parser.parse_args()
    
    config = load_config(args.config)
    main(config)