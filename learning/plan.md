# Learning Plan: Path to AI Architecture Leadership

## Current State Assessment

### Strengths (leverage these)
- **AI application layer:** Built a production-grade AI-augmented TPM system with multiple LLM providers, MCP integrations, and API connections
- **Systems thinking:** Spatial reasoning 90th percentile, CliftonStrengths Strategic + Ideation + Futuristic
- **Communication:** Can explain complex technical concepts clearly (CliftonStrengths #1)
- **Tool integration:** Deep experience with Cursor, Claude Code, OpenAI API, Gemini, MCPs, Glean
- **Cross-functional leadership:** 90% management & leadership EPP match

### Gaps (close these)
- **ML fundamentals:** Understanding of model architectures, training, fine-tuning, evaluation
- **AI infrastructure:** Model serving, vector databases, embedding pipelines, RAG at scale
- **Cloud architecture:** AWS/GCP/Azure certifications, infrastructure as code
- **Software engineering depth:** While not needed as a primary skill, deeper coding ability strengthens AI architecture credibility
- **Formal AI/ML vocabulary:** Being able to speak the language of ML engineers fluently

## Learning Roadmap

### Phase 1: Foundations (Weeks 1-4)

**Goal:** Speak ML fluently enough for technical conversations.

| Week | Topic | Resources | Output |
|------|-------|-----------|--------|
| 1 | ML fundamentals | [fast.ai Practical Deep Learning](https://course.fast.ai/), [3Blue1Brown Neural Networks](https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi) | Notes in this repo |
| 2 | LLM architecture | [Attention Is All You Need](https://arxiv.org/abs/1706.03762), [Andrej Karpathy's LLM lectures](https://www.youtube.com/@AndrejKarpathy) | Write an explainer doc |
| 3 | Prompt engineering & RAG | [Anthropic's prompt engineering guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering), [LangChain docs](https://python.langchain.com/) | Build a RAG prototype |
| 4 | AI agents & tool use | [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling), [MCP specification](https://modelcontextprotocol.io/) | Extend existing MCP knowledge |

### Phase 2: Architecture (Weeks 5-8)

**Goal:** Understand how to design and evaluate AI systems at scale.

| Week | Topic | Resources | Output |
|------|-------|-----------|--------|
| 5 | Vector databases & embeddings | Pinecone/Weaviate/Qdrant docs, embedding model comparison | Benchmark different vector DBs |
| 6 | ML pipelines & MLOps | [MLOps maturity model](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model), Kubeflow, MLflow | Architecture diagram for typical ML pipeline |
| 7 | Model serving & inference | vLLM, TensorRT, ONNX, model optimization | Document tradeoffs for different serving approaches |
| 8 | AI system design patterns | [Chip Huyen's Designing ML Systems](https://www.oreilly.com/library/view/designing-machine-learning/9781098107956/) | Design doc for a hypothetical AI system |

### Phase 3: Cloud & Infrastructure (Weeks 9-12)

**Goal:** Get cloud-certified, understand infrastructure for AI workloads.

| Week | Topic | Resources | Output |
|------|-------|-----------|--------|
| 9-10 | AWS Solutions Architect Associate | [AWS training](https://aws.amazon.com/training/), Stephane Maarek's course | Pass certification exam |
| 11 | AI-specific cloud services | AWS Bedrock/SageMaker, GCP Vertex AI, Azure AI Studio | Comparison matrix |
| 12 | Infrastructure as Code | Terraform basics, Pulumi | Deploy a simple AI service |

### Phase 4: Portfolio & Credibility (Ongoing)

**Goal:** Demonstrate knowledge publicly.

- [ ] Write 2-3 blog posts on AI architecture topics (Medium or personal blog)
- [ ] Build and open-source a non-trivial AI project
- [ ] Contribute to an AI open-source project (LangChain, LlamaIndex, etc.)
- [ ] Give a talk or workshop on AI-augmented workflows (meetup level)
- [ ] Get AWS Solutions Architect Associate certified

## Skill Matrix: Current vs. Target

| Skill | Current (1-5) | Target (1-5) | Priority |
|-------|--------------|--------------|----------|
| LLM API usage | 4 | 5 | Medium |
| Prompt engineering | 4 | 5 | Medium |
| MCP/tool integration | 5 | 5 | Maintain |
| ML model fundamentals | 2 | 4 | High |
| AI system architecture | 2 | 4 | High |
| Cloud infrastructure (AWS/GCP) | 2 | 4 | High |
| Vector DBs & RAG | 3 | 4 | Medium |
| MLOps/ML pipelines | 1 | 3 | High |
| Python (data/ML) | 3 | 4 | Medium |
| System design | 3 | 4 | Medium |
| Stakeholder management | 4 | 5 | Low |
| Program management | 4 | 4 | Maintain |
| Communication/storytelling | 5 | 5 | Maintain |

## Time Investment

- **Daily:** 1-2 hours learning (morning, before job applications)
- **Weekly:** One hands-on project or lab
- **Monthly:** One certification milestone or portfolio piece

## Tracking

Update this plan weekly. Move completed items to a "Done" section. Adjust based on what interview feedback reveals about market expectations.
