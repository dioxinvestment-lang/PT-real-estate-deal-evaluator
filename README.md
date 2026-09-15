# Portugal Real Estate Deal Evaluator

A Streamlit web app based on the **Deal evaluator PM.xlsx** underwriting model. It evaluates acquisition, Portuguese purchase costs, financing, renovation, resale returns, exit-price sensitivity, and downside stress.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud

1. Create a new GitHub repository.
2. Upload `app.py`, `requirements.txt`, and this `README.md` to the repository root.
3. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub.
4. Select the repository, choose `app.py`, and deploy.

## Important

This is an investment screening tool, not tax, legal, banking, valuation, or investment advice. The automatic IMT brackets reproduce the 2026 mainland assumptions in the source workbook. Verify current tax brackets and project-specific VAT eligibility before relying on the output.
