# HTMX Notes

## Element Removal with `hx-swap="outerHTML"`

-   **Problem:** An element targeted by `hx-delete` with `hx-swap="outerHTML"` was not being removed from the DOM, even though the server initially returned a `204 No Content` status.
-   **Cause:** According to HTMX documentation ([hx-delete attribute](https://htmx.org/attributes/hx-delete/)), a `204 No Content` response specifically tells HTMX *not* to perform the swap.
-   **Solution:** To make HTMX remove the element when using `hx-swap="outerHTML"`, the server **must** respond with a `200 OK` status code and an **empty response body**.

**Example (FastAPI):**

```python
# Incorrect for outerHTML removal:
# return Response(status_code=204)

# Correct for outerHTML removal:
return Response(content='', status_code=200)
```
