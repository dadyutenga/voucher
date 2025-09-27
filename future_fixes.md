# Update the register_user function:

@router.post("/register", response_model=schemas.Account)
def register_user(user: schemas.AccountCreate, db: Session = Depends(get_db)):
    """Register a new user with mobile number and password"""
    
    # Normalize mobile number - ensure it doesn't have + sign to match database format
    if user.mobile_number.startswith('+'):
        user.mobile_number = user.mobile_number[1:]
    
    # Check if user already exists
    db_user = db.query(Account).filter(Account.mobile_number == user.mobile_number).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Mobile number already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = Account(
        mobile_number=user.mobile_number,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

    