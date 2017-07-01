#! /bin/sh

find f in exp*.sh
do
	bash f &
done

tail -f *.log
