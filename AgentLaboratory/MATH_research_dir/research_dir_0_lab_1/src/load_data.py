from datasets import load_dataset

# Load the external HuggingFace dataset for MATH500 test set
MATH_test_set = load_dataset("HuggingFaceH4/MATH-500")["test"]

# Print basic information about the dataset to ensure it's loaded correctly
print("Total test questions:", len(MATH_test_set))
print("Example test question:", MATH_test_set[0])