// S3 Direct Upload Configuration
const s3Config = {
  uploadUrl: "",

  bucketUrl: "",

  maxFileSize: 5 * 1024 * 1024,
};

// API Configuration
const apiConfig = {
  baseUrl: "http://localhost:5001/api",
  endpoints: {
    login: "/login",
    register: "/register",
    products: "/products",
  },
};
