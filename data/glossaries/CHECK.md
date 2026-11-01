# Glossary check

One row per glossary entry. Please check that:
1. "Correct English" really is what the term means in that field.
2. The example sentence sounds like something a Korean speaker would actually say.
3. "Wrong meanings" are real everyday meanings a generic translator could pick.

Fix the JSON file directly if something is off. Notes marked ⚠️ are entries worth a closer look.

## CS (`cs.json`)

| Domain | Korean term | Correct English (this domain) | Wrong meanings | Example Korean sentence | English translation of the sentence |
|---|---|---|---|---|---|
| cs | 배열 | array | arrangement, layout | 배열의 첫 번째 원소는 인덱스 0이에요. | The first element of the array is at index 0. |
| cs | 함수 | function | (none — loanword-style term, no common everyday meaning) | 이 함수는 리스트를 정렬해서 반환해요. | This function sorts the list and returns it. |
| cs | 스레드 | thread | yarn | 스레드 두 개가 같은 변수에 동시에 접근하면 문제가 생겨요. | If two threads access the same variable at once, you get a problem. |
| cs | 상수 | constant | tap water, skilled player | 파이는 상수로 선언하는 게 좋아요. | It's better to declare pi as a constant. |
| cs | 정수 | integer | purified water, essence | 입력을 정수로 변환해 주세요. | Convert the input to an integer. |
| cs | 실수 | real number | mistake | 나눗셈 결과는 실수로 나와요. | The result of the division comes out as a real number (float). |
| cs | 변수 | variable | unexpected factor | 이 변수는 루프 밖에서 선언해야 해요. | This variable has to be declared outside the loop. |
| cs | 인자 | argument | factor | 이 함수는 인자를 두 개 받아요. | This function takes two arguments. |
| cs | 반환 | return | give back, refund | 못 찾으면 -1을 반환합니다. | If it isn't found, it returns -1. |
| cs | 큐 | queue | cue | 요청을 큐에 넣고 순서대로 처리해요. | We put requests in a queue and process them in order. |
| cs | 힙 | heap | hip | 우선순위 큐는 보통 힙으로 구현해요. | A priority queue is usually implemented with a heap. |
| cs | 캐시 | cache | cash | 캐시에 있으면 디스크를 읽을 필요가 없어요. | If it's in the cache, there's no need to read from disk. |
| cs | 버그 | bug | insect | 어제 배포한 코드에 버그가 있었어요. | There was a bug in the code we deployed yesterday. |
| cs | 열 | column | fever, heat | 테이블에 열을 하나 추가했어요. | I added a column to the table. |
| cs | 행 | row | bound for | 조건에 맞는 행만 가져오세요. | Fetch only the rows that match the condition. |
| cs | 대입 | assignment | substitution, college admission | x에 5를 대입하고 출력해 보세요. | Assign 5 to x and print it. |
| cs | 사전 | dictionary | in advance | 파이썬 사전은 키와 값을 저장해요. | A Python dictionary stores keys and values. |
| cs | 재귀 | recursion | returning | 이 문제는 재귀로 풀면 간단해요. | This problem is simple if you solve it with recursion. |
| cs | 주석 | comment | annotation, tin | 코드에 주석 좀 달아 주세요. | Please add some comments to the code. |
| cs | 소스 | source code | sauce | 소스 좀 깃허브에 올려 주세요. | Please push the source code to GitHub. |
| cs | 객체 | object | entity | 이 객체를 JSON으로 변환해 주세요. | Convert this object to JSON. |
| cs | 정점 | vertex | peak, summit | 그래프에 정점이 다섯 개 있어요. | The graph has five vertices. |
| cs | 간선 | edge | arterial road, trunk line | 두 정점 사이에 간선을 추가하세요. | Add an edge between the two vertices. |
| cs | 루트 | root | route | 트리의 루트부터 탐색을 시작해요. | We start the search from the root of the tree. |
| cs | 키 | key | height | 이 키가 딕셔너리에 있는지 확인해 보세요. | Check whether this key is in the dictionary. |
| cs | 값 | value | price | 이 키에 해당하는 값을 가져오세요. | Get the value for this key. |
| cs | 정렬 | sort | alignment | 배열을 오름차순으로 정렬하세요. | Sort the array in ascending order. |
| cs | 분기 | branch | quarter (of a year) | 여기서 조건에 따라 분기해요. | Here it branches depending on the condition. |
| cs | 배포 | deployment | distribution, handing out | 오늘 밤에 서버에 배포할게요. | I'll deploy to the server tonight. |
| cs | 풀 | pull | pool, grass, glue | 작업하기 전에 풀 먼저 받으세요. | Pull first before you start working. |
| cs | 모델 | model | fashion model | 모델을 더 큰 데이터로 다시 학습시켰어요. | We retrained the model on more data. |
| cs | 학습 | training | learning, studying | 모델 학습에 세 시간 걸렸어요. | Training the model took three hours. |
| cs | 손실 | loss | damage | 에폭마다 손실이 줄어들고 있어요. | The loss is going down every epoch. |
| cs | 추론 | inference | reasoning, deduction | 추론 속도가 너무 느려요. | Inference is too slow. |
| cs | 층 | layer | floor, story | 층을 하나 더 쌓으면 성능이 좋아질까요? | Would performance improve if we stack one more layer? |
| cs | 편향 | bias | prejudice | 가중치와 편향을 초기화하세요. | Initialize the weights and biases. |
| cs | 차원 | dimension | level | 임베딩 벡터는 768차원이에요. | The embedding vectors are 768-dimensional. |
| cs | 동기 | synchronous | motivation, peer | 이 함수는 동기 방식이라 응답을 기다려요. | This function is synchronous, so it waits for the response. |
| cs | 호출 | call | summon, page | API를 너무 많이 호출하면 요금이 나와요. | If you call the API too many times, you get charged. |
| cs | 비트 | bit | beat | 정수는 32비트로 저장돼요. | Integers are stored in 32 bits. |
| cs | 문자 | character | text message, letter | 문자열에서 첫 번째 문자만 잘라 주세요. | Take just the first character of the string. |
| cs | 탐색 | search | exploration, reconnaissance | 너비 우선 탐색으로 최단 경로를 찾아요. | We find the shortest path with breadth-first search. |
| cs | 프론트 | frontend | front desk | 프론트는 제가 맡을게요. | I'll take care of the frontend. |
| cs | 컨테이너 | container | shipping container | 도커 컨테이너가 계속 죽어요. | The Docker container keeps crashing. |
| cs | 이슈 | issue | hot topic | 깃허브에 이슈 하나 열어 주세요. | Please open an issue on GitHub. |
| cs | 병합 | merge | annexation | 두 브랜치를 병합하면 충돌이 나요. | Merging the two branches causes a conflict. |
| cs | 참조 | reference | consultation | 이 변수는 원본 객체를 참조하고 있어요. | This variable references the original object. |
| cs | 메모리 | memory | recollection | 메모리가 부족해서 프로그램이 죽었어요. | The program crashed because it ran out of memory. |

⚠️ **CS entries with more than one technical meaning:**
- **정렬**: means *sort* for data, but *alignment* in UI/CSS talk (가운데 정렬 = center alignment).
- **풀**: means *pull* in git talk (풀 받다, 풀 리퀘스트), but *pool* in 스레드 풀 / 커넥션 풀.
- **분기**: git branches are usually called 브랜치, so 분기 mostly comes up for code branching (if/else).

## Medicine (`med.json`)

| Domain | Korean term | Correct English (this domain) | Wrong meanings | Example Korean sentence | English translation of the sentence |
|---|---|---|---|---|---|
| med | 열 | fever | heat, column | 환자가 어젯밤부터 열이 39도까지 올랐어요. | The patient's fever has risen to 39 degrees since last night. |
| med | 음성 | negative | voice, audio | 코로나 검사 결과 음성이에요. | The COVID test result is negative. |
| med | 양성 | positive | benign, both sexes | 검사 결과 양성이 나와서 격리가 필요합니다. | The test came back positive, so isolation is needed. |
| med | 소견 | findings | opinion, view | CT 소견상 특이 사항은 없습니다. | There is nothing notable in the CT findings. |
| med | 처방 | prescription | remedy, solution | 항생제를 일주일치 처방해 드릴게요. | I'll prescribe you a week's worth of antibiotics. |
| med | 장 | intestine | chapter, chief, market | 장에 염증이 있어서 설사가 계속돼요. | There's inflammation in the intestines, so the diarrhea keeps going. |
| med | 위 | stomach | above, up | 위 내시경 검사를 받으셔야 해요. | You need to have an upper endoscopy (stomach scope). |
| med | 간 | liver | seasoning, between | 간 수치가 많이 높게 나왔어요. | Your liver enzyme levels came out very high. |
| med | 폐 | lung | nuisance | 폐에 물이 차 있어요. | There's fluid in the lungs. |
| med | 신장 | kidney | height, expansion | 신장 기능이 떨어져서 투석을 고려해야 합니다. | Kidney function has declined, so we need to consider dialysis. |
| med | 수액 | IV fluid | sap | 탈수가 심해서 수액을 맞으셔야 해요. | You're badly dehydrated, so you need IV fluids. |
| med | 주사 | injection | drunken behavior, scanning | 팔에 주사 놓을게요. | I'm going to give you an injection in the arm. |
| med | 호전 | improvement | belligerence | 항생제를 쓴 후 증상이 많이 호전됐어요. | The symptoms have improved a lot since starting antibiotics. |
| med | 결석 | stone | absence | 신장에 결석이 있어서 통증이 심한 거예요. | The pain is severe because there's a stone in the kidney. |
| med | 외래 | outpatient | foreign | 퇴원하고 2주 뒤에 외래로 오세요. | Come to the outpatient clinic two weeks after discharge. |
| med | 전이 | metastasis | transition, transfer | 암이 림프절로 전이됐습니다. | The cancer has metastasized to the lymph nodes. |
| med | 조직 | tissue | organization | 조직 검사 결과는 일주일 뒤에 나와요. | The tissue biopsy results will be ready in a week. |
| med | 변 | stool | change, side | 변에 피가 섞여 나와요. | There's blood in the stool. |
| med | 차트 | medical chart | graph, music chart | 환자 차트에 알레르기 기록해 두세요. | Record the allergy in the patient's chart. |
| med | 바이탈 | vital signs | vital | 바이탈 체크하고 보고해 주세요. | Check the vital signs and report back. |

⚠️ **양성** has two medical meanings: 陽性 = *positive* (test result) and 良性 = *benign* (양성 종양 = benign tumor). The glossary picks "positive" as the default because test results come up far more often, but "benign" is not truly wrong in medicine. The translator should use the next word (종양, 결절 → benign; 검사, 반응 → positive) if it can.

## Academia (`academia.json`)

| Domain | Korean term | Correct English (this domain) | Wrong meanings | Example Korean sentence | English translation of the sentence |
|---|---|---|---|---|---|
| academia | 실수 | real number | mistake | x는 모든 실수에 대해 정의됩니다. | x is defined for all real numbers. |
| academia | 정수 | integer | purified water, essence | n은 양의 정수라고 가정합시다. | Let's assume n is a positive integer. |
| academia | 상수 | constant | tap water, skilled player | 여기서 C는 적분 상수입니다. | Here, C is the constant of integration. |
| academia | 근 | root | muscle, approximately | 이 방정식의 근을 구하세요. | Find the roots of this equation. |
| academia | 극한 | limit | extreme | x가 0으로 갈 때 극한값을 구해 보세요. | Find the limit as x approaches 0. |
| academia | 행렬 | matrix | procession, line of people | 이 행렬의 역행렬을 구하세요. | Find the inverse of this matrix. |
| academia | 열 | column | fever, heat | 행렬의 두 번째 열을 보세요. | Look at the second column of the matrix. |
| academia | 행 | row | bound for | 첫 번째 행에 2를 곱하세요. | Multiply the first row by 2. |
| academia | 미분 | differentiation | fine powder | 이 함수를 x에 대해 미분하세요. | Differentiate this function with respect to x. |
| academia | 집합 | set | gathering, assembly | 이 집합의 원소는 세 개예요. | This set has three elements. |
| academia | 원 | circle | won (currency), wish | 반지름이 r인 원의 넓이는 파이 r제곱이에요. | The area of a circle with radius r is pi r squared. |
| academia | 변 | side | stool, change | 이 삼각형은 세 변의 길이가 같아요. | All three sides of this triangle are the same length. |
| academia | 정리 | theorem | organizing, summary | 피타고라스 정리를 쓰면 쉽게 풀려요. | It's easy to solve with the Pythagorean theorem. |
| academia | 가정 | assumption | family, household | 이 가정이 틀리면 결론도 성립하지 않아요. | If this assumption is wrong, the conclusion doesn't hold either. |
| academia | 해 | solution | sun, year, harm | 이 연립방정식은 해가 없어요. | This system of equations has no solution. |
| academia | 수렴 | convergence | gathering (of opinions) | 이 급수는 수렴합니다. | This series converges. |
| academia | 발산 | divergence | release (of stress or energy) | n이 커지면 이 수열은 발산해요. | As n grows, this sequence diverges. |
| academia | 학회 | academic conference | academic society, student club | 다음 달에 학회에서 논문 발표해요. | I'm presenting my paper at a conference next month. |
| academia | 심사 | review | judging, screening | 논문이 지금 심사 중이에요. | The paper is currently under review. |
| academia | 조교 | teaching assistant | drill instructor | 과제 질문은 조교한테 메일 보내세요. | Email the TA with questions about the assignment. |
| academia | 함수 | function | (none) | 이 함수의 정의역을 구하세요. | Find the domain of this function. |
| academia | 내적 | dot product | internal, inner | 두 벡터의 내적을 구하세요. | Find the dot product of the two vectors. |
| academia | 외적 | cross product | external, outward | 외적의 결과는 벡터예요. | The result of a cross product is a vector. |
| academia | 공간 | space | room, gap | 이 벡터들은 3차원 공간을 생성해요. | These vectors span three-dimensional space. |
| academia | 사상 | mapping | ideology, thought | 이 선형 사상은 일대일이에요. | This linear mapping is one-to-one. |
| academia | 대수 | algebra | majority, large number | 이번 학기에 대수 수업을 들어요. | I'm taking an algebra class this semester. |
| academia | 기저 | basis | base, underlying | 이 두 벡터가 평면의 기저가 돼요. | These two vectors form a basis for the plane. |
| academia | 분산 | variance | dispersion, distribution | 표본의 분산을 계산하세요. | Compute the variance of the sample. |
| academia | 표본 | sample | specimen | 표본 크기가 너무 작아요. | The sample size is too small. |
| academia | 급수 | series | grade, rank | 이 급수의 합을 구하세요. | Find the sum of this series. |
| academia | 항 | term | port, item | 첫째 항이 1이고 공비가 2예요. | The first term is 1 and the common ratio is 2. |
| academia | 계수 | coefficient | counting | x제곱의 계수는 3이에요. | The coefficient of x squared is 3. |
| academia | 차수 | degree | number of times, order | 이 다항식의 차수는 4예요. | The degree of this polynomial is 4. |
| academia | 근사 | approximation | cool, stylish | 테일러 급수로 근사하면 오차가 작아요. | If you approximate with a Taylor series, the error is small. |
| academia | 연속 | continuous | consecutive | 이 함수는 x=0에서 연속이에요. | This function is continuous at x = 0. |
| academia | 독립 | independent | independence (of a country) | 두 사건은 서로 독립이에요. | The two events are independent of each other. |

⚠️ **학회**: "academic society" is also a valid meaning (e.g. 한국물리학회 = Korean Physical Society). "Conference" is the default because in speech "학회 가요" almost always means going to a conference.
