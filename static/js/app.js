// Main application logic
function appState() {
    return {
        // State
        products: [],
        isLoggedIn: false,
        currentUser: null,
        activeModal: null, // 'login', 'register', 'product', 'viewProduct', 'deleteConfirm'
        currentProduct: {},
        isSubmitting: false,
        uploadProgress: null,
        selectedFile: null,
        
        // Form models
        loginForm: {
            username: '',
            password: ''
        },
        registerForm: {
            username: '',
            email: '',
            password: ''
        },
        productForm: {
            id: null,
            name: '',
            description: '',
            price: '',
            product_image_url: ''
        },
        
        // Error messages
        loginError: null,
        registerError: null,
        productError: null,
        
        // Toast notification
        toast: {
            show: false,
            message: '',
            type: 'success', // 'success' or 'error'
            timeout: null
        },
        
        // Lifecycle hooks
        init() {
            // Check if user is already logged in
            this.checkAuthStatus();
            // Load products
            this.fetchProducts();
        },
        
        // Authentication methods
        checkAuthStatus() {
            const token = localStorage.getItem('access_token');
            const userData = localStorage.getItem('user_data');
            
            if (token && userData) {
                this.isLoggedIn = true;
                this.currentUser = JSON.parse(userData);
            }
        },
        
        // Refresh token when access token expires
        refreshToken() {
            return new Promise((resolve, reject) => {
                const refreshToken = localStorage.getItem('refresh_token');
                
                if (!refreshToken) {
                    reject(new Error('No refresh token available'));
                    return;
                }
                
                fetch(`${apiConfig.baseUrl}/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${refreshToken}`
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Token refresh failed');
                    }
                    return response.json();
                })
                .then(data => {
                    // Store new tokens
                    localStorage.setItem('access_token', data.access_token);
                    if (data.refresh_token) {
                        localStorage.setItem('refresh_token', data.refresh_token);
                    }
                    resolve(data.access_token);
                })
                .catch(error => {
                    console.error('Token refresh failed:', error);
                    // If refresh fails, redirect to login
                    this.logout();
                    this.activeModal = 'login';
                    this.showToast('Your session has expired. Please log in again.', 'error');
                    reject(error);
                });
            });
        },
        
        login() {
            this.isSubmitting = true;
            this.loginError = null;
            
            fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.login}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.loginForm)
            })
            .then(response => response.json())
            .then(data => {
                if (data.access_token) {
                    // Store tokens and user data
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('refresh_token', data.refresh_token);
                    localStorage.setItem('user_data', JSON.stringify(data.user));
                    
                    // Update app state
                    this.isLoggedIn = true;
                    this.currentUser = data.user;
                    this.activeModal = null;
                    
                    // Reset form
                    this.loginForm = { username: '', password: '' };
                    
                    // Show success message
                    this.showToast('Login successful', 'success');
                } else {
                    this.loginError = data.msg || 'Login failed';
                }
            })
            .catch(error => {
                console.error('Login error:', error);
                this.loginError = 'An error occurred during login';
            })
            .finally(() => {
                this.isSubmitting = false;
            });
        },
        
        register() {
            this.isSubmitting = true;
            this.registerError = null;
            
            fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.register}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.registerForm)
            })
            .then(response => response.json())
            .then(data => {
                if (response.status === 201) {
                    // Registration successful
                    this.activeModal = 'login';
                    this.registerForm = { username: '', email: '', password: '' };
                    this.showToast('Registration successful. Please log in.', 'success');
                } else {
                    this.registerError = data.msg || 'Registration failed';
                }
            })
            .catch(error => {
                console.error('Registration error:', error);
                this.registerError = 'An error occurred during registration';
            })
            .finally(() => {
                this.isSubmitting = false;
            });
        },
        
        logout() {
            // Clear local storage
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user_data');
            
            // Reset app state
            this.isLoggedIn = false;
            this.currentUser = null;
            
            // Show notification
            this.showToast('You have been logged out', 'success');
        },
        
        // Product CRUD methods
        fetchProducts() {
            fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.products}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                this.products = data;
            })
            .catch(error => {
                console.error('Error fetching products:', error);
                this.showToast('Failed to load products', 'error');
            });
        },
        
        viewProduct(product) {
            this.currentProduct = product;
            this.activeModal = 'viewProduct';
        },
        
        addProduct() {
            // Reset form
            this.productForm = {
                id: null,
                name: '',
                description: '',
                price: '',
                product_image_url: ''
            };
            this.uploadProgress = null;
            this.selectedFile = null;
            this.productError = null;
            this.activeModal = 'product';
        },
        
        editProduct(product) {
            this.productForm = {
                id: product.id,
                name: product.name,
                description: product.description,
                price: product.price,
                product_image_url: product.product_image_url
            };
            this.uploadProgress = null;
            this.selectedFile = null;
            this.productError = null;
            this.activeModal = 'product';
        },
        
        confirmDelete(product) {
            this.currentProduct = product;
            this.activeModal = 'deleteConfirm';
        },
        
        saveProduct() {
            this.isSubmitting = true;
            this.productError = null;
            
            const method = this.productForm.id ? 'PUT' : 'POST';
            const url = this.productForm.id 
                ? `${apiConfig.baseUrl}${apiConfig.endpoints.products}/${this.productForm.id}`
                : `${apiConfig.baseUrl}${apiConfig.endpoints.products}`;
            
            // Upload image first if selected
            if (this.selectedFile) {
                this.uploadImageToS3()
                    .then(imageUrl => {
                        this.productForm.product_image_url = imageUrl;
                        this.saveProductToAPI(url, method);
                    })
                    .catch(error => {
                        console.error('Error uploading image:', error);
                        this.productError = 'Failed to upload image';
                        this.isSubmitting = false;
                    });
            } else {
                this.saveProductToAPI(url, method);
            }
        },
        
        saveProductToAPI(url, method) {
            this.authenticatedFetch(url, {
                method: method,
                body: JSON.stringify({
                    name: this.productForm.name,
                    description: this.productForm.description,
                    price: parseFloat(this.productForm.price),
                    product_image_url: this.productForm.product_image_url
                })
            })
            .then(response => {
                const isOk = response.ok;
                return response.json().then(data => ({ data, isOk }));
            })
            .then(({ data, isOk }) => {
                if (isOk) {
                    // Success
                    this.activeModal = null;
                    this.fetchProducts(); // Refresh products list
                    this.showToast(
                        this.productForm.id ? 'Product updated successfully' : 'Product created successfully', 
                        'success'
                    );
                } else {
                    // Error
                    this.productError = data.msg || 'Failed to save product';
                }
            })
            .catch(error => {
                console.error('Error saving product:', error);
                this.productError = 'An error occurred while saving the product';
            })
            .finally(() => {
                this.isSubmitting = false;
            });
        },
        
        deleteProduct() {
            this.isSubmitting = true;
            
            this.authenticatedFetch(`${apiConfig.baseUrl}${apiConfig.endpoints.products}/${this.currentProduct.id}`, {
                method: 'DELETE'
            })
            .then(response => {
                const isOk = response.ok;
                return response.json().then(data => ({ data, isOk }));
            })
            .then(({ data, isOk }) => {
                if (isOk) {
                    this.activeModal = null;
                    this.fetchProducts(); // Refresh products list
                    this.showToast('Product deleted successfully', 'success');
                } else {
                    this.showToast(data.msg || 'Failed to delete product', 'error');
                }
            })
            .catch(error => {
                console.error('Error deleting product:', error);
                this.showToast('An error occurred while deleting the product', 'error');
            })
            .finally(() => {
                this.isSubmitting = false;
            });
        },
        
        // S3 Image Upload
        handleFileChange(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            // Validate file type - only accept images
            if (!file.type.match('image.*')) {
                this.showToast('Please select an image file', 'error');
                return;
            }
            
            // Validate file size
            if (file.size > s3Config.maxFileSize) {
                this.showToast(`Image is too large. Maximum size is ${s3Config.maxFileSize / (1024*1024)}MB`, 'error');
                return;
            }
            
            this.selectedFile = file;
            
            // Preview the image
            const reader = new FileReader();
            reader.onload = e => {
                this.productForm.product_image_url = e.target.result; // For preview only
            };
            reader.readAsDataURL(this.selectedFile);
        },
        
        uploadImageToS3() {
            return new Promise((resolve, reject) => {
                if (!this.selectedFile) {
                    // No file selected, return the existing URL
                    resolve(this.productForm.product_image_url);
                    return;
                }
                
                this.uploadProgress = 0;
                
                // Exactly follow the example implementation
                const reader = new FileReader();
                
                reader.onload = async (e) => {
                    try {
                        // Make sure we have an image
                        if (!e.target.result.includes('data:image')) {
                            reject(new Error('Selected file is not an image'));
                            return;
                        }
                        
                        // Size validation
                        if (e.target.result.length > s3Config.maxFileSize) {
                            reject(new Error('Image is too large'));
                            return;
                        }
                        
                        // Step 1: Get the pre-signed URL
                        const response = await fetch(s3Config.uploadUrl);
                        const data = await response.json();
                        
                        if (!data.uploadURL) {
                            throw new Error('Failed to get upload URL');
                        }
                        
                        // Step 2: Create binary data (copied exactly from the example)
                        let binary = atob(e.target.result.split(',')[1]);
                        let array = [];
                        for (let i = 0; i < binary.length; i++) {
                            array.push(binary.charCodeAt(i));
                        }
                        let blobData = new Blob([new Uint8Array(array)], {type: 'image/jpeg'});
                        
                        // Step 3: Upload directly using fetch with PUT method
                        this.showToast('Uploading image...', 'info');
                        
                        // Use the exact fetch approach from the example
                        const uploadResult = await fetch(data.uploadURL, {
                            method: 'PUT',
                            body: blobData
                        });
                        
                        if (!uploadResult.ok) {
                            throw new Error(`Upload failed with status ${uploadResult.status}`);
                        }
                        
                        // Final URL is without query string
                        const imageUrl = data.uploadURL.split('?')[0];
                        this.showToast('Upload complete', 'success');
                        resolve(imageUrl);
                    } catch (error) {
                        console.error('Error uploading image:', error);
                        this.showToast('Failed to upload image', 'error');
                        reject(error);
                    }
                };
                
                reader.onerror = () => {
                    reject(new Error('Failed to read file'));
                };
                
                // Read the file as data URL
                reader.readAsDataURL(this.selectedFile);
            });
        },
        
        // Utility method for authenticated API calls with token refresh
        authenticatedFetch(url, options = {}) {
            // Set default options
            const fetchOptions = {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            };
            
            // Add authorization header if not already present
            if (!fetchOptions.headers.Authorization) {
                const token = localStorage.getItem('access_token');
                if (token) {
                    fetchOptions.headers.Authorization = `Bearer ${token}`;
                }
            }
            
            // Make the API call
            return fetch(url, fetchOptions)
                .then(response => {
                    // If unauthorized, try to refresh token
                    if (response.status === 401) {
                        return this.refreshToken()
                            .then(newToken => {
                                // Update authorization header with new token
                                fetchOptions.headers.Authorization = `Bearer ${newToken}`;
                                
                                // Retry the request with new token
                                return fetch(url, fetchOptions);
                            })
                            .catch(error => {
                                throw error; // Re-throw to be caught by the caller
                            });
                    }
                    return response;
                });
        },
        
        // Toast notification
        showToast(message, type = 'success') {
            // Clear any existing timeout
            if (this.toast.timeout) {
                clearTimeout(this.toast.timeout);
            }
            
            // Set toast data
            this.toast.show = true;
            this.toast.message = message;
            this.toast.type = type;
            
            // Auto-hide after 3 seconds
            this.toast.timeout = setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        }
    };
}
