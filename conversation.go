package domain

//Сущность: Conversation(id, order_id, partcipant_ids, created_at)

type Conversation struct {
	id             		int
	order_id       		int
	partcipant_ids 		[]int
	created_at     		string
}
