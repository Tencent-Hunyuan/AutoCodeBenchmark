# AutoCodeGen: An Automated LLM-Sandbox Workflow for Code Dataset Synthesis

<div align="center">
  <img src="../figures/autocodegen.png" width="95%">
</div>


## 1. Generating Code Solutions
### 1.1 constructing messages
```python
python3 src/build_msg_for_solution.py \
    --raw_code_file data/seeds/python.jsonl \
    --raw_code_msg_file data/solutions/python_msg.jsonl \
    --lang python \
    --mode gen_code_solution
```

### 1.2 calling deepseek-v3-0324
```python
python3 src/call_api.py \
    --input data/solutions/java_msg.jsonl \
    --output data/solutions/java_output.jsonl
```


### 1.3 parsing output
```python
python3 src/extract_three_code_blocks.py \
    --input data/solutions/python_output.jsonl \
    --output data/solutions/python_solution.jsonl
```


## 2. Generating Test Functions
### 2.1 calling sandbox for obtaining test output
```python
python3 src/call_sandbox.py \
    --input_file data/solutions/python_solution.jsonl \
    --output data/solutions/python_test_output.jsonl \
    --solution_key canonical_solution \
    --concurrency 256
```

### 2.2 constructing messages for combining test input and output
```python
python3 src/build_msg_for_test.py \
    --raw_code_file data/solutions/python_test_output.jsonl \
    --raw_code_msg_file data/tests/python_msg.jsonl \
    --lang python \
    --mode gen_test_function
```

### 2.3 calling deepseek-v3-0324 for combining test input and output
```python
python3 src/call_api.py \
    --input data/tests/java_msg.jsonl \
    --output data/tests/java_output.jsonl
```

### 2.4 extracting demo and full test functions
```python
python3 src/extract_two_code_blocks.py \
    --input data/tests/python_output.jsonl \
    --output data/tests/python_test_func.jsonl
```

### 2.5 calling sandbox for verifing correctness
```python
python3 src/call_sandbox.py \
    --input_file data/tests/python_test_func.jsonl \
    --output data/tests/python_test_exec.jsonl \
    --solution_key canonical_solution
```

### 2.6 filtering out incorrect data
```python
python3 src/filter_data.py \
    --input data/tests/python_test_exec.jsonl \
    --output data/questions/python.jsonl
```


## 3. Generating Programming Problem

### 3.1 constructing messages
```python
python3 src/build_msg_for_question.py \
    --raw_code_file data/questions/python.jsonl \
    --raw_code_msg_file data/questions/python_msg.jsonl \
    --lang python
```

### 3.2 calling deepseek-V3-0324
```python
python3 src/call_api.py \
    --input data/questions/java_msg.jsonl \
    --output data/questions/java_output.jsonl
```

### 3.3 extracting programming question
```python
python3 src/extract_question.py \
    --input data/questions/python_output.jsonl \
    --output data/questions/python_question.jsonl
```

## Other

### Programming Languages Translation

```python
python3 src/build_msg_for_translation.py \
    --raw_code_file data/questions/python_question.jsonl \
    --raw_code_msg_file data/translations/racket_msg.jsonl \
    --source_lang python \
    --target_lang racket
```

```python
python3 src/call_api.py \
    --input data/translations/julia_msg.jsonl \
    --output data/translations/julia_output.jsonl
```

### Tagging

```
templates/tagging.txt
```

### LLM-as-Critic

```
templates/critic.txt
```