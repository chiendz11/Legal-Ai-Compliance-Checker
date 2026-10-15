# BRD section 13: evaluation skeleton

Reserve offline evaluation pipelines for requirement coverage, temporal accuracy, retrieval Recall@K, criterion/compliance F1, grounding, citation validation/temporal accuracy, risk precision and recommendation validity. Current tests verify software contracts, upstream boundaries and persistence; they do not measure these model/data quality metrics.

Steps 5–7 are now module skeletons. The old engine-dependent tests were removed; the unused CLI placeholders have been removed. The team must implement real evaluators alongside its modules. Frozen QA references remain available for writing those evaluators.

Skeleton only; no adapter/UI implementation is provided here.
