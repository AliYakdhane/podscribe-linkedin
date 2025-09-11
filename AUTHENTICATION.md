# 🔐 Authentication System

This Streamlit app now includes a secure login system to protect access to the podcast transcript puller.

## 🚀 Quick Setup

### 1. Generate Your Password Hash

Run the password hash generator:

```bash
python generate_password_hash.py
```

Enter your desired password when prompted. The script will generate a secure hash.

### 2. Update the App Configuration

Copy the generated hash to `streamlit_app.py`:

```python
ADMIN_PASSWORD_HASH = "your_generated_hash_here"
```

### 3. Deploy with Your Credentials

The app will now require login with:
- **Username:** `admin`
- **Password:** Your chosen password

## 🔒 Security Features

### **Password Security**
- ✅ **SHA-256 Hashing** - Passwords are never stored in plain text
- ✅ **HMAC Comparison** - Prevents timing attacks
- ✅ **Secure Session Management** - Sessions expire after 1 hour

### **Session Management**
- ✅ **Automatic Timeout** - Sessions expire after 1 hour of inactivity
- ✅ **Secure Logout** - Clears all session data
- ✅ **Session Validation** - Checks authentication on every page load

### **Access Control**
- ✅ **Login Required** - No access without authentication
- ✅ **Session Persistence** - Stays logged in during active use
- ✅ **Automatic Logout** - Logs out when session expires

## 🎯 How It Works

### **Login Process**
1. User visits the app
2. Login form is displayed
3. User enters username and password
4. Password is hashed and compared securely
5. If valid, session is created with timestamp
6. User gains access to the main app

### **Session Management**
1. Every page load checks authentication
2. Session timeout is validated
3. If expired, user is logged out automatically
4. Logout button clears all session data

### **Security Measures**
- Passwords are hashed with SHA-256
- HMAC comparison prevents timing attacks
- Sessions have automatic expiration
- All session data is cleared on logout

## 🛠️ Customization

### **Change Username**
Edit the `ADMIN_USERNAME` variable in `streamlit_app.py`:

```python
ADMIN_USERNAME = "your_username"
```

### **Change Session Timeout**
Edit the `SESSION_TIMEOUT` variable in `streamlit_app.py`:

```python
SESSION_TIMEOUT = 7200  # 2 hours in seconds
```

### **Add Multiple Users**
To support multiple users, you can modify the authentication logic to use a dictionary of usernames and password hashes.

## 🚨 Security Best Practices

1. **Use Strong Passwords** - Choose a complex password with mixed characters
2. **Keep Credentials Secure** - Don't share your login details
3. **Regular Updates** - Change passwords periodically
4. **Monitor Access** - Check logs for unauthorized access attempts
5. **Secure Deployment** - Use HTTPS in production

## 🔧 Troubleshooting

### **Login Issues**
- Verify the password hash is correct
- Check that the username matches exactly
- Ensure the hash was copied completely

### **Session Issues**
- Sessions expire after 1 hour by default
- Refresh the page to check authentication status
- Use the logout button to clear session data

### **Deployment Issues**
- Ensure the password hash is set in production
- Check that all authentication code is deployed
- Verify session state is working properly

## 📱 User Experience

### **Login Screen**
- Clean, professional login form
- Clear error messages for invalid credentials
- Responsive design for all devices

### **Main App**
- Logout button in sidebar
- Session status indicator
- Seamless experience after login

### **Security Indicators**
- Lock icon in page title
- Security messages in login form
- Clear logout confirmation

## 🎉 Benefits

- **Protects Your Data** - Only authorized users can access the app
- **Professional Appearance** - Clean, secure login interface
- **Easy to Use** - Simple login process for users
- **Secure by Default** - Built-in security best practices
- **Customizable** - Easy to modify for your needs

Your podcast transcript puller is now secure and protected! 🔒
