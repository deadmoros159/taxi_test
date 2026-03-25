package domain

type Role struct {
	passenger bool
	driver    bool
}

type Participant struct {
	//Participant (conversation_id, user_id, role passenger/driver)
	conversation_id 	int
	user_id         	int
	role            	Role
}
