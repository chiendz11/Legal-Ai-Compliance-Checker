/** MSW mocks the API from local fixtures only when VITE_API_MOCK=true. Never in production builds. */
export const mockEnabled = import.meta.env.DEV && import.meta.env.VITE_API_MOCK === "true";
