# 글꼴

| 파일 | 글꼴 | 출처 |
|---|---|---|
| NotoSansKR-Variable.ttf | Noto Sans KR (굵기 가변) | github.com/google/fonts `ofl/notosanskr` |
| NotoSerifKR-Variable.ttf | Noto Serif KR (굵기 가변) | github.com/google/fonts `ofl/notoserifkr` |
| OFL.txt | SIL Open Font License 1.1 | 같은 저장소 |

두 글꼴 모두 SIL OFL 1.1이라 프로그램에 함께 넣어 배포할 수 있다(OFL.txt를 같이 둔다).
실행할 때 `gui/theme.py`의 `load_fonts()`가 이 폴더의 .ttf/.otf를 등록하고, 파일이 없으면 Malgun Gothic을 쓴다.
