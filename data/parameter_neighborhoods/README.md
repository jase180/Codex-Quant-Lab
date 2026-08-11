# Parameter Neighborhoods

Parameter neighborhoods are small prespecified sets used by campaign candidate
generation. They are not optimized search grids.

Rules:

- Keep values small and justified before execution.
- Do not add new values after seeing a result from the same campaign.
- Prefer `unknown` or blocked catalog entries over fake precision.
- Let the campaign candidate generator choose from these neighborhoods later;
  do not treat them as executable strategy JSON.
