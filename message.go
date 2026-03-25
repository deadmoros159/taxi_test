package domain

type Message struct {
	//Message (id, conversation_id, sender_id, text, created_at)
	id              	int
	conversation_id 	int
	sender_id       	int
	text            	string
	created_at      	string
}
