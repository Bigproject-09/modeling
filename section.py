#!/usr/bin/env python3
"""
PDF 파싱 JSON 파일을 목차 기반으로 섹션별로 분리하는 도구
목차의 넘버링 형식(1.1, 가나다, I.II.III 등)을 자동으로 인식하여 섹션을 분리합니다.
"""

import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class Section:
    """문서의 한 섹션을 나타내는 클래스"""
    section_number: str  # 목차에서 읽어온 번호 (예: "1.1", "가", "I")
    title: str
    content: List[str]  # 텍스트 및 표 포함
    start_page: int
    end_page: int
    
    def to_dict(self):
        return asdict(self)
    
    def to_text(self) -> str:
        """섹션을 텍스트로 변환"""
        text = f"{'='*80}\n"
        text += f"섹션 {self.section_number}: {self.title}\n"
        text += f"페이지: {self.start_page + 1} ~ {self.end_page + 1}\n"
        text += f"{'='*80}\n\n"
        text += "\n".join(self.content)
        return text


class SectionSplitter:
    """PDF 파싱 결과를 목차 기반으로 섹션별로 분리하는 클래스"""
    
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self.pages = self._load_json()
        
        # 목차 헤더 패턴
        self.toc_patterns = [
            r'^목\s*차$',
            r'^<\s*목\s*차\s*>$',
            r'^contents?$',
            r'^table\s+of\s+contents?$',
            r'^\[목\s*차\]$',
            r'^【목\s*차】$',
        ]
        
        # 범용 섹션 번호 추출 패턴 (매우 광범위하게)
        # 이 패턴들은 목차에서 "번호. 제목" 형식을 추출하는 데 사용됩니다
        self.section_extraction_patterns = [
            # 숫자 기반: 1., 1.1., 1.1.1., 1-1., 1-1-1. 등
            r'^([\d]+(?:[.\-][\d]+)*)[.\s]\s*(.+)$',
            
            # 한글: 가., 나., 다. 또는 (가), (나), (다)
            r'^([가-힣])[.\)]\s*(.+)$',
            r'^\(([가-힣])\)\s*(.+)$',
            
            # 로마자: I., II., III. 또는 i., ii., iii.
            r'^([IVXivx]+)[.\)]\s*(.+)$',
            r'^\(([IVXivx]+)\)\s*(.+)$',
            
            # 알파벳: A., B., C. 또는 a., b., c.
            r'^([A-Za-z])[.\)]\s*(.+)$',
            r'^\(([A-Za-z])\)\s*(.+)$',
            
            # 혼합: 1-가., 1-a. 등
            r'^([\d]+[.\-][가-힣A-Za-z])[.\)]\s*(.+)$',
            
            # 번호만 (제목 없이): 1, 2, 3 (다음 줄에 제목이 올 가능성 있음)
            r'^([\d]+(?:[.\-][\d]+)*)$',
        ]
    
    def _load_json(self) -> List[Dict]:
        """JSON 파일 로드"""
        with open(self.json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _is_toc_header(self, text: str) -> bool:
        """목차 헤더인지 확인"""
        text_clean = text.strip()
        for pattern in self.toc_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return True
        return False
    
    def _extract_number_and_title(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        텍스트에서 섹션 번호와 제목 추출
        목차에서 읽어온 실제 형식을 그대로 사용
        """
        text_clean = text.strip()
        
        for pattern in self.section_extraction_patterns:
            match = re.match(pattern, text_clean)
            if match:
                if len(match.groups()) == 2:
                    return match.group(1), match.group(2).strip()
                elif len(match.groups()) == 1:
                    # 번호만 있고 제목이 없는 경우
                    return match.group(1), None
        
        return None, None
    
    def _normalize_text_for_comparison(self, text: str) -> str:
        """텍스트를 정규화하여 비교 (공백, 특수문자 제거)"""
        return re.sub(r'[^\w가-힣]', '', text.lower())
    
    def extract_toc(self) -> Dict[str, str]:
        """
        목차에서 섹션 번호와 제목 추출
        목차에 사용된 넘버링 형식을 그대로 추출
        """
        toc = {}
        in_toc = False
        pending_number = None  # 번호만 있고 제목이 다음 줄에 오는 경우를 위한 버퍼
        
        for page in self.pages:
            for text in page['texts']:
                text_stripped = text.strip()
                
                # 목차 시작 감지
                if self._is_toc_header(text_stripped):
                    in_toc = True
                    continue
                
                # 목차 내에서 섹션 추출
                if in_toc:
                    # 페이지 번호로 목차 종료 감지
                    if re.match(r'^-?\d+\s*-?$', text_stripped):
                        in_toc = False
                        pending_number = None
                        continue
                    
                    # 이전에 번호만 있었다면 이번 줄을 제목으로 사용
                    if pending_number:
                        if text_stripped and not re.match(r'^[\d\s\-\.]+$', text_stripped):
                            toc[pending_number] = text_stripped
                            pending_number = None
                            continue
                    
                    # 번호와 제목 추출
                    number, title = self._extract_number_and_title(text_stripped)
                    
                    if number:
                        if title:
                            toc[number] = title
                        else:
                            # 번호만 있고 제목이 없으면 다음 줄 대기
                            pending_number = number
        
        return toc
    
    def _is_section_match(self, text: str, section_num: str, toc_title: str) -> bool:
        """
        텍스트가 목차의 특정 섹션과 일치하는지 확인
        번호와 제목이 모두 일치해야 함
        """
        number, title = self._extract_number_and_title(text.strip())
        
        if not number or number != section_num:
            return False
        
        # 제목이 없거나 일치하면 True
        if not title:
            return True
        
        # 제목 유사도 확인 (정규화된 텍스트로 비교)
        normalized_extracted = self._normalize_text_for_comparison(title)
        normalized_toc = self._normalize_text_for_comparison(toc_title)
        
        # 제목이 정확히 일치하거나, 서로 포함관계이거나, 매우 유사하면 True
        return (normalized_extracted == normalized_toc or 
                normalized_extracted in normalized_toc or 
                normalized_toc in normalized_extracted)
    
    def split_into_sections(self) -> List[Section]:
        """
        문서를 섹션별로 분리
        목차가 있으면 목차 기준으로, 없으면 전체를 하나의 섹션으로
        """
        toc = self.extract_toc()
        
        if not toc:
            print("목차를 찾을 수 없습니다. 전체 문서를 하나의 섹션으로 처리합니다.")
            return [self._create_full_document_section()]
        
        print(f"발견된 목차 항목: {len(toc)}개")
        for num, title in toc.items():
            print(f"   {num}. {title}")
        
        sections = []
        current_section = None
        in_toc_area = False
        
        for page in self.pages:
            page_idx = page['page_index']
            
            for text in page['texts']:
                text_stripped = text.strip()
                
                # 목차 영역 스킵
                if self._is_toc_header(text_stripped):
                    in_toc_area = True
                    continue
                
                if in_toc_area:
                    if re.match(r'^-?\d+\s*-?$', text_stripped):
                        in_toc_area = False
                    continue
                
                # 새로운 섹션 시작 감지 (목차에 있는 섹션만)
                section_started = False
                for section_num, toc_title in toc.items():
                    if self._is_section_match(text_stripped, section_num, toc_title):
                        # 이전 섹션 저장
                        if current_section:
                            current_section.end_page = page_idx - 1 if page_idx > current_section.start_page else page_idx
                            sections.append(current_section)
                        
                        # 새 섹션 시작
                        current_section = Section(
                            section_number=section_num,
                            title=toc_title,
                            content=[],
                            start_page=page_idx,
                            end_page=page_idx
                        )
                        section_started = True
                        break
                
                # 섹션 헤더는 content에 포함하지 않음
                if section_started:
                    continue
                
                # 현재 섹션에 내용 추가
                if current_section:
                    # 페이지 번호 같은 불필요한 텍스트 필터링
                    if not re.match(r'^-?\d+\s*-?$', text_stripped):
                        current_section.content.append(text)
                        current_section.end_page = page_idx
        
        # 마지막 섹션 저장
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _create_full_document_section(self) -> Section:
        """목차가 없을 때 전체 문서를 하나의 섹션으로 생성"""
        content = []
        for page in self.pages:
            content.extend(page['texts'])
        
        return Section(
            section_number="0",
            title="전체 문서",
            content=content,
            start_page=0,
            end_page=len(self.pages) - 1
        )
    
    def save_sections(self, output_path: str, format: str = 'json'):
        """섹션을 파일로 저장"""
        sections = self.split_into_sections()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'json':
            # JSON 형식으로 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump([s.to_dict() for s in sections], f, ensure_ascii=False, indent=2)
            print(f"\n{len(sections)}개 섹션을 JSON 형식으로 저장: {output_path}")
        
        elif format == 'text':
            # 텍스트 형식으로 저장 (각 섹션을 별도 파일로)
            for section in sections:
                # 파일명에 사용할 수 있도록 섹션 번호 정제
                safe_section_num = re.sub(r'[^\w\-]', '_', section.section_number)
                section_file = output_path.parent / f"{output_path.stem}_section_{safe_section_num}.txt"
                with open(section_file, 'w', encoding='utf-8') as f:
                    f.write(section.to_text())
            print(f"\n{len(sections)}개 섹션을 텍스트 파일로 저장: {output_path.parent}")
        
        elif format == 'combined_text':
            # 모든 섹션을 하나의 텍스트 파일로 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                for section in sections:
                    f.write(section.to_text())
                    f.write("\n\n")
            print(f"\n{len(sections)}개 섹션을 하나의 텍스트 파일로 저장: {output_path}")
        
        return sections


def verify_sections(sections: List[Section], verbose: bool = True):
    """
    섹션 분리가 잘 되었는지 상세하게 검증
    
    Args:
        sections: 검증할 섹션 리스트
        verbose: 상세 출력 여부
    """
    if verbose:
        print("\n" + "="*80)
        print("섹션 분리 검증 결과")
        print("="*80)
    
    # 기본 통계
    print(f"\n총 섹션 수: {len(sections)}")
    
    if not sections:
        print("오류: 섹션이 하나도 생성되지 않았습니다.")
        return False
    
    # 각 섹션 정보
    if verbose:
        print("\n" + "-"*80)
        print("각 섹션 상세 정보:")
        print("-"*80)
    
    all_valid = True
    total_content_items = 0
    total_tables = 0
    empty_sections = []
    
    for i, section in enumerate(sections, 1):
        content_count = len(section.content)
        total_content_items += content_count
        
        # 표 개수 확인
        table_count = sum(1 for item in section.content if '[TABLE START]' in item)
        total_tables += table_count
        
        if verbose:
            print(f"\n{i}. 섹션 {section.section_number}: {section.title}")
            print(f"페이지: {section.start_page + 1} ~ {section.end_page + 1}")
            print(f"컨텐츠 항목: {content_count}개")
            
            if table_count > 0:
                print(f"표: {table_count}개")
            
            # 내용이 비어있는 섹션 경고
            if content_count == 0:
                print(f"경고: 이 섹션은 내용이 비어있습니다")
                empty_sections.append(section.section_number)
            
            # 내용 미리보기
            if content_count > 0:
                preview_text = '\n'.join(section.content)[:150].replace('\n', ' ')
                print(f"미리보기: {preview_text}...")
    
    # 전체 통계
    print("\n" + "="*80)
    print("전체 통계")
    print("="*80)
    print(f"총 표 개수: {total_tables}")
    print(f"총 컨텐츠 항목: {total_content_items}")
    
    if empty_sections:
        print(f"\n내용이 비어있는 섹션: {len(empty_sections)}개")
        print(f"   섹션 번호: {', '.join(empty_sections)}")
    
    # 섹션 연속성 검증
    print("\n" + "-"*80)
    print("섹션 연속성 검증:")
    print("-"*80)
    
    gaps = []
    for i in range(len(sections) - 1):
        current_end = sections[i].end_page
        next_start = sections[i+1].start_page
        
        if current_end + 1 < next_start:
            gap_pages = list(range(current_end + 1, next_start))
            gaps.append({
                'after_section': sections[i].section_number,
                'before_section': sections[i+1].section_number,
                'missing_pages': gap_pages
            })
            print(f"섹션 {sections[i].section_number}과 {sections[i+1].section_number} 사이에 누락된 페이지 발견")
            print(f"누락 페이지: {[p+1 for p in gap_pages]}")
    
    if not gaps:
        print("모든 섹션이 연속적으로 연결되어 있습니다")
    
    # 페이지 범위 검증
    print("\n" + "-"*80)
    print("페이지 범위 검증:")
    print("-"*80)
    
    invalid_ranges = []
    for section in sections:
        if section.start_page > section.end_page:
            invalid_ranges.append(section)
            print(f"섹션 {section.section_number}: 시작 페이지({section.start_page + 1})가 끝 페이지({section.end_page + 1})보다 큽니다")
    
    if not invalid_ranges:
        print("모든 섹션의 페이지 범위가 유효합니다")
    
    # 최종 판정
    print("\n" + "="*80)
    
    if len(sections) == 1 and sections[0].section_number == "0":
        print("목차가 없어 전체 문서를 하나의 섹션으로 처리했습니다")
        return True
    
    if empty_sections or gaps or invalid_ranges:
        print("경고: 일부 문제가 발견되었습니다. 위 내용을 확인해주세요.")
        all_valid = False
    else:
        print("모든 검증 통과! 섹션 분리가 성공적으로 완료되었습니다.")
    
    print("="*80 + "\n")
    
    return all_valid



def main():
    parser = argparse.ArgumentParser(
        description='PDF 파싱 JSON 파일을 목차 기반으로 섹션별로 분리',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # JSON 형식으로 저장 및 검증
  python pdf_section_splitter.py input.json output_sections.json
  
  # 검증만 수행 (저장 안함)
  python pdf_section_splitter.py input.json --verify-only
  
  # 텍스트 형식으로 저장 (각 섹션 별도 파일)
  python pdf_section_splitter.py input.json output_sections.txt --format text
  
  # 간단한 검증 결과만 보기
  python pdf_section_splitter.py input.json --verify-only --quiet

주의사항:
  - 이 도구는 목차에서 읽어온 넘버링 형식을 그대로 사용합니다
  - 1.1, 가나다, I.II.III 등 모든 형식을 지원합니다
  - 목차가 없으면 전체 문서를 하나의 섹션으로 처리합니다
        """
    )
    
    parser.add_argument('input', help='입력 JSON 파일 경로')
    parser.add_argument('output', nargs='?', help='출력 파일 경로')
    parser.add_argument('--format', choices=['json', 'text', 'combined_text'], 
                        default='json', help='출력 형식 (기본값: json)')
    parser.add_argument('--verify-only', action='store_true', 
                        help='섹션 분리 검증만 수행하고 저장하지 않음')
    parser.add_argument('--quiet', action='store_true',
                        help='간단한 검증 결과만 출력')
    
    args = parser.parse_args()
    
    # 입력 파일 확인
    if not Path(args.input).exists():
        print(f"오류: 입력 파일을 찾을 수 없습니다: {args.input}")
        return 1
    
    # 섹션 분리 수행
    print(f"PDF 파일 분석 중: {args.input}")
    splitter = PDFSectionSplitter(args.input)
    
    if args.verify_only:
        sections = splitter.split_into_sections()
        verify_sections(sections, verbose=not args.quiet)
    else:
        if not args.output:
            print("오류: 출력 파일 경로를 지정해주세요")
            print("또는 --verify-only 옵션을 사용하세요")
            return 1
        
        sections = splitter.save_sections(args.output, args.format)
        verify_sections(sections, verbose=not args.quiet)