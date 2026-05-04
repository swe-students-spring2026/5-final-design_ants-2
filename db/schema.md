users {
\_id: string,
username: string,
email: string,
created_at: datetime,
credits: int
}
rooms {
\_id: string,
name: string,
floor: string,
capacity: int,
current_crowd: int | null,
current_quiet: int | null,
last_updated: datetime | null
}
checkins {
\_id: ObjectId,
user_id: string,
room_id: string,
time: datetime,
crowdedness: int,
quietness: int
}
