from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import re
import csv
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 세션을 위한 시크릿 키

# 환경변수 로드
load_dotenv()

# 관리자 설정
ADMIN_PASSWORD = "1234"  # 실제 사용시 더 복잡한 비밀번호로 변경

# PDF 경로와 벡터 저장 디렉토리 설정
JSON_PATH = "rag_input_sample.json"
VECTOR_DIR = "vectorstore"
embeddings = OpenAIEmbeddings()

# 관리자 인증 데코레이터
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 챗봇 가드레일 클래스
class ChatbotGuardrails:
    def __init__(self):
        # 복지용구 관련 키워드
        self.welfare_keywords = [
            '복지', '용구', '신청', '등급', '부담', '자격', '품목', '보조', '지원',
            '노인', '장애', '의료', '재활', '보장', '수급', '급여', '서비스',
            '욕창', '매트리스', '방석', '보행기', '휠체어', '침대', '변기', '목욕',
            '산소', '호흡기', '발생기', '치료', '의료기기', '보장구'
        ]
        
        # 카테고리별 키워드 정의 (더 구체적으로)
        self.category_keywords = {
            '신청방법': ['신청방법', '신청 방법', '신청 절차', '신청 서류', '신청서', '제출', '접수', '처리', '어떻게 신청', '신청하려면'],
            '품목': ['품목', '종류', '제품', '기구', '장비', '보조기구', '재활용품', '어떤 것들', '품목에는', '종류에는'],
            '등급신청조건': ['등급', '등급 신청', '등급 조건', '등급 기준', '등급 판정', '등급 인정', '등급 요건', '자격조건', '신청 조건', '조건'],
            '본인부담률': ['본인부담률', '부담률', '본인 부담', '비용', '금액', '요금', '가격', '얼마', '비용', '할인', '부담'],
            '자격확인': ['자격', '자격 확인', '확인', '조사', '검토', '심사', '평가', '판단', '가능한지', '신청 가능']
        }
        
        # 금지 키워드 (명백히 부적절한 내용만)
        self.forbidden_keywords = [
            '욕설', '비속어', '음란', '선정적', '폭력', '혐오', '차별', '정치', '종교'
        ]
        
        # 예시 질문들 (초기 가이드라인)
        self.example_questions = [
            "복지용구 신청 방법이 궁금해요",
            "복지용구 품목에는 어떤 것들이 있나요?",
            "복지용구 등급 신청 조건은 어떻게 되나요?",
            "복지용구 본인부담률은 얼마인가요?",
            "복지용구 자격 확인은 어떻게 하나요?",
            "복지용구 신청 서류는 무엇이 필요한가요?",
            "복지용구 수급자 자격은 어떻게 되나요?",
            "복지용구 급여 서비스는 어떻게 받을 수 있나요?"
        ]
        
        # 사용자별 마지막 질문 추적 (중복 방지용)
        self.user_last_questions = {}
        self.user_last_timestamps = {}
    
    def validate_question(self, question: str, user_id: str = "default") -> Dict[str, Any]:
        """질문 유효성 검증"""
        question = question.strip()
        
        # 1. 길이 검증
        if len(question) <= 3:
            return {
                'valid': False,
                'message': '질문을 좀 더 구체적으로 작성해주세요. (예: "복지용구 신청 방법이 궁금해요")',
                'examples': self.get_random_examples(3)
            }
        
        # 2. 의미없는 단어 검증
        meaningless_patterns = [r'^[아어음그저]+$', r'^[?!]+$', r'^[가-힣]{1,2}$']
        for pattern in meaningless_patterns:
            if re.match(pattern, question):
                return {
                    'valid': False,
                    'message': '구체적인 질문을 해주세요. 복지용구와 관련된 궁금한 점이 있으시면 언제든 물어보세요!',
                    'examples': self.get_random_examples(3)
                }
        
        # 3. 금지 키워드 검증
        for keyword in self.forbidden_keywords:
            if keyword in question:
                return {
                    'valid': False,
                    'message': '죄송합니다. 저는 노인복지용구 관련 질문에만 답변할 수 있어요. 복지용구와 관련된 궁금한 점이 있으시면 언제든 물어보세요!',
                    'examples': self.get_random_examples(3)
                }
        
        # 4. GPT 기반 관련성 검증
        relevance_check = self.check_welfare_relevance(question)
        if not relevance_check['is_relevant']:
            return {
                'valid': False,
                'message': relevance_check['message'],
                'examples': self.get_random_examples(3)
            }
        
        return {'valid': True, 'message': '질문이 유효합니다.'}
    
    def check_welfare_relevance(self, question: str) -> Dict[str, Any]:
        """GPT를 사용하여 복지용구 관련성 검증"""
        try:
            from langchain_openai import ChatOpenAI
            
            # 빠른 응답을 위해 간단한 모델 사용
            llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, max_tokens=50)
            
            relevance_prompt = f"""
다음 질문이 노인복지용구와 관련이 있는지 판단해주세요.

노인복지용구란: 노인의 일상생활을 돕는 의료기기나 보조기구 (휠체어, 침대, 보행기, 욕창방지용품, 안전손잡이 등)
관련 주제: 복지용구 신청, 등급, 비용, 품목, 자격조건, 사용법, 대여/구입 등

질문: "{question}"

답변 형식:
- 관련 있음: "YES"
- 관련 없음: "NO"

답변:"""

            response = llm.invoke(relevance_prompt)
            result = response.content.strip().upper()
            
            if "YES" in result:
                return {
                    'is_relevant': True,
                    'message': '복지용구 관련 질문입니다.'
                }
            else:
                return {
                    'is_relevant': False,
                    'message': '죄송합니다. 저는 노인복지용구 전문 상담 챗봇입니다. 복지용구 신청, 품목, 비용, 자격조건 등에 대해서만 답변할 수 있어요. 복지용구와 관련된 궁금한 점이 있으시면 언제든 물어보세요!'
                }
                
        except Exception as e:
            print(f"관련성 검증 오류: {e}")
            # 오류 시 안전하게 허용 (기존 RAG에서 처리)
            return {
                'is_relevant': True,
                'message': '검증 중 오류가 발생했지만 진행합니다.'
            }
    
    def verify_and_correct_answer(self, question: str, answer: str) -> str:
        """답변을 검증하고 필요시 교정"""
        try:
            from langchain_openai import ChatOpenAI
            
            # 빠른 검증용 모델
            llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, max_tokens=150)
            
            verify_prompt = f"""
다음 답변에 명백한 오류가 있는지만 검증해주세요. 새로운 정보를 추가하지 마세요.

검증 기준:
1. 전동휠체어를 복지용구라고 했는가? (오류 - 전동휠체어는 의료기기)
2. 복지용구가 아닌 것을 복지용구라고 했는가?
3. 명백히 틀린 사실이 있는가?

질문: "{question}"
답변: "{answer}"

검증 결과 (둘 중 하나만):
- "PASS" (답변에 명백한 오류 없음)
- "BLOCK: [간단한 이유]" (명백한 오류 발견)

검증:"""

            response = llm.invoke(verify_prompt)
            result = response.content.strip()
            
            if result.startswith("BLOCK:"):
                # 오류 발견 시 올바른 정보로 재답변 시도
                reason = result.replace("BLOCK:", "").strip()
                print(f"🚨 답변 오류 발견: {reason}")
                print(f"🔄 올바른 정보로 재답변 시도...")
                
                # 올바른 정보로 다시 답변 생성
                corrected_answer = self.get_corrected_answer(question)
                return corrected_answer
            else:
                # 검증 통과 - 원본 답변 사용
                return answer
                
        except Exception as e:
            print(f"답변 검증 중 오류: {e}")
            # 검증 실패 시 원본 답변 그대로 반환
            return answer
    

    
    def classify_question(self, question: str, status: str = 'success') -> str:
        """질문을 카테고리별로 분류"""
        if status == 'fallback' or status == 'blocked':
            return '차단된질문'
        
        question_lower = question.lower()
        category_scores = {}
        
        # 각 카테고리별 점수 계산
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in question_lower:
                    score += 1
            category_scores[category] = score
        
        # 가장 높은 점수의 카테고리 반환
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category
        
        # 명확한 카테고리가 없으면 기타로 분류
        return '기타'
    
    def check_duplicate_question(self, question: str, user_id: str) -> Dict[str, Any]:
        """중복 질문 검증 (임시 비활성화)"""
        return {'valid': True, 'message': '중복 검증 통과'}
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산"""
        # 간단한 유사도 계산 (실제로는 더 정교한 알고리즘 사용)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0
    
    def get_random_examples(self, count: int = 3) -> list:
        """랜덤 예시 질문 반환"""
        import random
        return random.sample(self.example_questions, min(count, len(self.example_questions)))
    
    def get_welcome_examples(self) -> list:
        """환영 예시 질문 반환"""
        return self.example_questions[:5]
    
    def get_fallback_response(self, error_type: str) -> str:
        """오류 발생 시 대체 응답"""
        fallback_responses = {
            'search_error': '죄송합니다. 현재 검색에 문제가 있어요. 잠시 후 다시 시도해주세요.',
            'api_error': '죄송합니다. 서비스에 일시적인 문제가 있어요. 잠시 후 다시 시도해주세요.',
            'general_error': '죄송합니다. 예상치 못한 오류가 발생했어요. 잠시 후 다시 시도해주세요.'
        }
        return fallback_responses.get(error_type, fallback_responses['general_error'])

# 가드레일 인스턴스 생성
guardrails = ChatbotGuardrails()



def save_chat_log(question, answer, is_fallback=False):
    """채팅 로그를 CSV 파일에 저장"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "fallback" if is_fallback else "success"
    category = guardrails.classify_question(question, status)
    
    # 현재 파일의 디렉토리에서 CSV 파일 찾기
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, 'chat_log.csv')
    
    # CSV 파일이 없으면 헤더와 함께 생성
    file_exists = os.path.exists(csv_path)
    
    with open(csv_path, 'a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'question', 'answer', 'status', 'category'])
        writer.writerow([timestamp, question, answer, status, category])

def save_feedback_log(question, answer, feedback_type, user_id):
    """피드백 로그를 별도 CSV 파일에 저장"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 현재 파일의 디렉토리에서 피드백 로그 파일 찾기
    current_dir = os.path.dirname(os.path.abspath(__file__))
    feedback_path = os.path.join(current_dir, 'feedback_log.csv')
    
    # 파일이 없으면 헤더와 함께 생성
    file_exists = os.path.exists(feedback_path)
    
    with open(feedback_path, 'a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'question', 'answer', 'feedback_type', 'user_id'])
        writer.writerow([timestamp, question, answer, feedback_type, user_id])

def read_feedback_logs(limit=None):
    """피드백 로그를 읽어오기"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    feedback_path = os.path.join(current_dir, 'feedback_log.csv')
    
    if not os.path.exists(feedback_path):
        return []
    
    logs = []
    try:
        with open(feedback_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                logs.append({
                    'timestamp': row.get('timestamp', ''),
                    'question': row.get('question', ''),
                    'answer': row.get('answer', ''),
                    'feedback_type': row.get('feedback_type', ''),
                    'user_id': row.get('user_id', '')
                })
        
        # 최신 순으로 정렬
        logs.reverse()
        
        if limit:
            logs = logs[:limit]
        
        return logs
    except Exception as e:
        return []

def read_chat_logs(limit=None, category=None):
    """채팅 로그를 읽어오기"""
    # 현재 파일의 디렉토리에서 CSV 파일 찾기
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, 'chat_log.csv')
    
    if not os.path.exists(csv_path):
        return []
    
    logs = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # HTML 템플릿에서 필요한 모든 필드 포함
                simple_log = {
                    'timestamp': row.get('timestamp', ''),
                    'question': row.get('question', ''),
                    'answer': row.get('answer', ''),
                    'status': row.get('status', 'success'),
                    'category': row.get('category', '기타')
                }
                
                # 카테고리 필터링
                if category and category != 'all' and simple_log['category'] != category:
                    continue
                    
                logs.append(simple_log)
        
        # 최신 순으로 정렬
        logs.reverse()
        
        if limit:
            logs = logs[:limit]
        
        return logs
    except Exception as e:
        return []

# init_vectorstore 함수 수정
def init_vectorstore():
    if os.path.exists(VECTOR_DIR):
        vectorstore = FAISS.load_local(VECTOR_DIR, embeddings, allow_dangerous_deserialization=True)
        print("✅ 기존 벡터스토어 로드 완료")
    else:
        print("🛠️ 벡터스토어를 새로 생성합니다...")
        
        # JSON 파일 로드
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, JSON_PATH)
        print(f"📁 JSON 경로: {json_path}")
        print(f"📁 JSON 파일 존재: {os.path.exists(json_path)}")
        
        # JSON 파일 읽기
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 문서 생성 (배치 처리)
        vectorstore = None
        batch_size = 5  # 한 번에 5개씩 처리
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            print(f"📦 배치 {i//batch_size + 1}/{(len(data)-1)//batch_size + 1} 처리 중... ({len(batch)}개 문서)")
            
            docs = []
            for item in batch:
                # 첨부파일 내용 길이 제한 (너무 긴 파일은 잘라냄)
                content = f"제목: {item['title']}\n\n"
                content += f"URL: {item['url']}\n\n"
                
                # 내용 길이 제한 (10,000자로 제한)
                main_content = item['content'] or ''
                content += f"내용: {main_content}\n\n"
                
                # 첨부파일 내용 추가 (각 파일당 5,000자로 제한)
                if 'attachments' in item and item['attachments']:
                    for attachment in item['attachments']:
                        content += f"첨부파일: {attachment['file_name']}\n\n"
                        file_text = attachment['text'] or ''
                        content += f"파일내용: {file_text}\n\n"
                
                # Document 객체 생성
                from langchain_core.documents import Document
                doc = Document(page_content=content, metadata={"source": item['title']})
                docs.append(doc)
            
            # 텍스트 분할
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=120)
            split_documents = text_splitter.split_documents(docs)
            print(f"✂️ 배치 분할 완료: {len(split_documents)} 청크")
            
            # 벡터스토어 생성 또는 추가
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(documents=split_documents, embedding=embeddings)
                    print(f"✅ 첫 번째 배치로 벡터스토어 생성")
                else:
                    vectorstore.add_documents(split_documents)
                    print(f"✅ 배치 추가 완료")
            except Exception as e:
                print(f"❌ 배치 처리 오류: {e}")
                if "max_tokens_per_request" in str(e):
                    print("🔄 청크 크기를 더 줄여서 재시도...")
                    # 청크 크기를 더 줄여서 재시도
                    smaller_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
                    split_documents = smaller_splitter.split_documents(docs)
                    if vectorstore is None:
                        vectorstore = FAISS.from_documents(documents=split_documents, embedding=embeddings)
                    else:
                        vectorstore.add_documents(split_documents)
                    print(f"✅ 작은 청크로 배치 처리 완료")
                else:
                    raise e
        
        print(f"📄 전체 JSON 로드 완료: {len(data)} 문서")
        
        # 벡터스토어 저장
        if vectorstore:
            vectorstore.save_local(VECTOR_DIR)
            print("✅ 벡터스토어 저장 완료")
        else:
            raise Exception("벡터스토어 생성 실패")
    
    return vectorstore

# 체인 초기화
def filter_relevant_context(question: str, retrieved_docs):
    """검색된 문서 중 질문과 실제로 관련있는 것만 필터링"""
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, max_tokens=100)
        
        filtered_docs = []
        
        for doc in retrieved_docs:
            # 각 문서가 질문과 관련있는지 검증
            filter_prompt = f"""
다음 질문과 문서 내용이 실제로 관련이 있는지 판단해주세요.

질문: "{question}"
문서 내용: "{doc.page_content[:500]}..."

답변: "관련있음" 또는 "관련없음"
"""
            
            response = llm.invoke(filter_prompt)
            result = response.content.strip()
            
            if "관련있음" in result:
                filtered_docs.append(doc)
                
        return filtered_docs[:10]  # 최대 10개만 사용
        
    except Exception as e:
        print(f"컨텍스트 필터링 오류: {e}")
        return retrieved_docs[:10]  # 오류 시 원본 사용

def init_chain():
    vectorstore = init_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 15})
    
    prompt = PromptTemplate.from_template(
        """너는 노인복지용구 및 장애인보조기기 전문 상담 챗봇이야. 


사용자의 질문에 대해서 제공된 자료(context)를 참고해서, 어르신들이 이해하기 쉽고 읽기 편하게 한국어로 설명해줘.

답변 작성 시 반드시 다음 마크다운 형식을 정확히 사용해주세요:

**1. 제목과 섹션:**
- 메인 제목: **제목**
- 섹션 제목: **섹션명:**
- 예시: **본인부담률:** 또는 **신청 자격:**

**2. 강조 표현:**
- 중요한 숫자나 키워드: **15%** 또는 **복지용구**
- 핵심 내용: **반드시 확인해야 할 사항**

**3. 목록과 체크리스트:**
- 일반 목록: • 항목
- 체크리스트: ✅ 항목 (줄바꿈 없이)
- 경고사항: ⚠️ 항목 (줄바꿈 없이)
- 연락처: 📞 항목 (줄바꿈 없이)
- 번호 목록: 1️⃣ 항목 (줄바꿈 없이)

**4. 구조화된 답변 예시:**
**섹션 제목:**

✅ **항목 1:** **내용**

✅ **항목 2:** **내용**

⚠️ **주의사항:** 구체적인 정보는 제공된 자료를 참고하세요.

📞 **문의:** 관련 기관에 확인해 주세요.

**주의:** 위는 형식 예시이며, 실제 답변에서는 제공된 context 정보를 정확히 사용하세요.

**중요:** 답변은 반드시 제공된 context 정보에 기반해야 하며, 정확성을 최우선으로 해주세요.

**5. 어르신 친화적 표현:**
- 존댓말 사용
- 복잡한 용어는 쉬운 말로 설명
- 충분히 자세하고 완전한 답변 제공
- 답변을 중간에 끊지 말고 완전히 마무리하기

**6. 안전장치:**
- 잘 모르는 내용은 추측하지 말고 "확실하지 않으니 공단에 문의해 주세요"라고 안내
- 복지용구 명칭이나 수급 조건은 명확하게 말해줘

**7. 답변 완성도:**
- 모든 질문에 대해 완전한 답변 제공
- 답변이 중간에 끊기지 않도록 주의
- 내용이 많더라도 답변을 완전히 마무리하기

답변 작성 시 반드시 다음 규칙을 지켜주세요:
1. 각 섹션마다 줄바꿈을 넣어주세요
2. 목록은 각 항목마다 줄바꿈을 넣어주세요
3. 마크다운 문법을 정확히 사용해주세요 (**굵은 글씨**, ✅, ⚠️ 등)
4. 읽기 쉽도록 적절한 공백을 넣어주세요
5. 답변은 반드시 끝까지 완성해주세요


#Context: 
{context}

#Question:
{question}

#Answer:"""
    )
    
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0, model_kwargs={"max_completion_tokens": 2000} )
    
    def get_filtered_context(question):
        docs = retriever.get_relevant_documents(question)
        filtered = filter_relevant_context(question, docs)
        return "\n\n".join([doc.page_content for doc in filtered])
    
    chain = (
        {"context": get_filtered_context, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain

# 전역 변수로 체인 저장
chain = init_chain()

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_logs'))
        else:
            return render_template('admin_login.html', error='비밀번호가 올바르지 않습니다.')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))

@app.route('/admin/logs')
@admin_required
def admin_logs():
    logs = read_chat_logs(limit=100)
    feedback_logs = read_feedback_logs(limit=100)
    
    # 간단한 통계 계산
    total_questions = len(logs)
    
    # 피드백 통계 계산
    like_count = len([f for f in feedback_logs if f['feedback_type'] == 'like'])
    dislike_count = len([f for f in feedback_logs if f['feedback_type'] == 'dislike'])
    
    return render_template('admin_logs.html', 
                         logs=logs, 
                         feedback_logs=feedback_logs,
                         total_questions=total_questions,
                         successful=total_questions,
                         blocked_errors=0,
                         success_rate=100.0,
                         categories={},
                         like_count=like_count,
                         dislike_count=dislike_count)

@app.route('/admin/api/logs')
@admin_required
def admin_api_logs():
    category = request.args.get('category')
    logs = read_chat_logs(limit=100, category=category)
    return jsonify({'logs': logs})

@app.route('/admin/api/feedback')
@admin_required
def admin_api_feedback():
    feedback_type = request.args.get('type')
    feedback_logs = read_feedback_logs()
    
    if feedback_type and feedback_type in ['like', 'dislike']:
        feedback_logs = [f for f in feedback_logs if f['feedback_type'] == feedback_type]
    
    return jsonify({'feedback_logs': feedback_logs})

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question', '').strip()
    user_id = data.get('user_id', 'web_user')
    
    if not question:
        return jsonify({'answer': '질문을 입력해주세요.', 'is_fallback': True, 'success': False})
    
    # 가드레일 검증
    validation = guardrails.validate_question(question, user_id)
    if not validation['valid']:
        response = {
            'answer': validation['message'],
            'is_fallback': True,
            'success': False
        }
        if 'examples' in validation:
            response['examples'] = validation['examples']
        if validation.get('is_duplicate', False):
            response['is_duplicate'] = True
        
        save_chat_log(question, validation['message'], is_fallback=True)
        return jsonify(response)
    

    
    try:
        # RAG 체인 실행
        answer = chain.invoke(question)
        save_chat_log(question, answer, is_fallback=False)
        return jsonify({'question': question, 'answer': answer, 'success': True})
    except Exception as e:
        print(f"Error: {e}")
        fallback_msg = guardrails.get_fallback_response('search_error')
        save_chat_log(question, fallback_msg, is_fallback=True)
        return jsonify({'answer': fallback_msg, 'is_fallback': True, 'success': False})

@app.route('/feedback', methods=['POST'])
def feedback():
    """피드백 처리 엔드포인트"""
    data = request.get_json()
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()
    feedback_type = data.get('feedback_type')
    is_cancel = data.get('is_cancel', False)
    user_id = data.get('user_id', 'web_user')
    
    if not question or not answer:
        return jsonify({'success': False, 'error': '질문과 답변이 필요합니다.'}), 400
    
    # 피드백 취소인 경우 빈 문자열로 설정
    if is_cancel:
        feedback_type = 'cancelled'
    
    # 피드백 로그 저장
    save_feedback_log(question, answer, feedback_type, user_id)
    
    return jsonify({'success': True, 'message': '피드백이 저장되었습니다.'})

@app.route('/examples', methods=['GET'])
def get_examples():
    examples = guardrails.get_welcome_examples()
    return jsonify({'examples': examples})

# 기존 벡터스토어 로드를 위한 전역 변수
vectorstore = None

def add_documents_to_vectorstore(new_documents):
    """기존 벡터스토어에 새로운 문서들을 추가"""
    global vectorstore
    
    if vectorstore is None:
        vectorstore = init_vectorstore()
    
    # 텍스트 분할
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=120)
    split_documents = text_splitter.split_documents(new_documents)
    
    # 기존 벡터스토어에 추가
    vectorstore.add_documents(split_documents)
    
    # 저장
    vectorstore.save_local(VECTOR_DIR)
    
    print(f"✅ 벡터스토어에 {len(split_documents)}개 청크 추가 완료")
    return True

def add_new_data_from_json(json_file_path):
    """새 JSON 파일의 데이터를 벡터스토어에 추가"""
    from langchain_core.documents import Document
    
    # JSON 파일 읽기
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 문서 생성
    docs = []
    for item in data:
        content = f"제목: {item['title']}\n\n"
        content += f"URL: {item['url']}\n\n" 
        content += f"내용: {item['content']}\n\n"
        
        # 첨부파일 내용 추가
        if 'attachments' in item and item['attachments']:
            for attachment in item['attachments']:
                content += f"첨부파일: {attachment['file_name']}\n\n"
                content += f"파일내용: {attachment['text']}\n\n"
                
        doc = Document(page_content=content, metadata={"source": item['title']})
        docs.append(doc)
    
    # 벡터스토어에 추가
    add_documents_to_vectorstore(docs)
    print(f"📄 {len(docs)}개 문서를 벡터스토어에 추가했습니다")
    return True

def add_text_to_vectorstore(title, content, url="", metadata=None):
    """텍스트를 직접 벡터스토어에 추가"""
    from langchain_core.documents import Document
    
    doc_content = f"제목: {title}\n\n"
    if url:
        doc_content += f"URL: {url}\n\n"
    doc_content += f"내용: {content}\n\n"
    
    if metadata is None:
        metadata = {"source": title}
    
    doc = Document(page_content=doc_content, metadata=metadata)
    add_documents_to_vectorstore([doc])
    print(f"📄 새 문서 '{title}' 추가 완료")
    return True

@app.route('/admin/add_data', methods=['POST'])
@admin_required  
def admin_add_data():
    """관리자가 새로운 데이터를 추가하는 엔드포인트"""
    try:
        data = request.get_json()
        
        if 'json_file' in data:
            # JSON 파일 경로로 추가
            json_file = data['json_file']
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, json_file)
            
            if os.path.exists(json_path):
                add_new_data_from_json(json_path)
                return jsonify({'success': True, 'message': f'{json_file}의 데이터를 추가했습니다'})
            else:
                return jsonify({'success': False, 'error': f'파일을 찾을 수 없습니다: {json_file}'})
                
        elif 'title' in data and 'content' in data:
            # 직접 텍스트로 추가
            title = data['title']
            content = data['content']
            url = data.get('url', '')
            
            add_text_to_vectorstore(title, content, url)
            return jsonify({'success': True, 'message': f'새 문서 "{title}"를 추가했습니다'})
        
        else:
            return jsonify({'success': False, 'error': '올바른 데이터 형식이 아닙니다 (title과 content 또는 json_file 필요)'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/rebuild_vectorstore', methods=['POST'])
@admin_required
def admin_rebuild_vectorstore():
    """벡터스토어를 완전히 재구축"""
    try:
        global vectorstore
        
        # 기존 벡터스토어 삭제
        if os.path.exists(VECTOR_DIR):
            import shutil
            shutil.rmtree(VECTOR_DIR)
            print("🗑️ 기존 벡터스토어 삭제")
        
        # 새로 생성
        vectorstore = init_vectorstore()
        
        # 체인도 새로 초기화
        global chain
        chain = init_chain()
        
        return jsonify({'success': True, 'message': '벡터스토어가 재구축되었습니다'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)